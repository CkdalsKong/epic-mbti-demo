import Combine
import Foundation

@MainActor
final class EPICDemoViewModel: ObservableObject {
    @Published var availablePersonas: [PersonaPreset] = []
    @Published var persona: PersonaPreset = PersonaLoader.fallbackPersona
    @Published var preferenceDrafts: [String] = []
    @Published var searchText = "Car"
    @Published var searchResults: [WikipediaResult] = []

    // ── Generation state ─────────────────────────────────────────────────
    @Published var generationQuestion = ""
    @Published var epicResponseText = ""
    @Published var ragResponseText = ""
    @Published var epicRetrievedDocs: [RetrievedDoc] = []
    @Published var ragRetrievedDocs: [RetrievedDoc] = []
    @Published var topPreference = ""
    @Published var isGenerating = false
    @Published var generationError: String?
    @Published var generationComplete = false
    // Retrieval stats from server
    @Published var epicRetrLatencyMs: Double?
    @Published var ragRetrLatencyMs: Double?
    @Published var epicIndexBytes: Int?
    @Published var ragIndexBytes: Int?
    @Published var epicEntryCount: Int?
    @Published var ragChunkCount: Int?

    // ── Evaluation state ─────────────────────────────────────────────────
    @Published var evaluationResult: EvaluationResult?
    @Published var isEvaluating = false
    @Published var evaluationError: String?

    private let generationRuntime = GenerationRuntime()
    @Published var selectedArticle: WikiArticle?
    @Published var chunks: [DocumentChunk] = []
    @Published var existingEntries: [ExistingMemoryEntry] = []
    @Published var coarseCandidates: [CoarseCandidate] = []
    @Published var fineEvaluations: [FineEvaluation] = []
    @Published var epicEntries: [EPICMemoryEntry] = []
    @Published var coarseThreshold = 0.30
    @Published var isLoading = false
    @Published var isRunningEPIC = false
    @Published var statusMessage = "PrefWiki preset loaded."
    @Published var errorMessage: String?
    @Published var runtimeFootprint: RealEPICFootprint?
    @Published var runProgress: EPICRunProgress = .idle
    @Published var chunkProgress: [Int: EPICChunkProgress] = [:]
    @Published var activeChunkIndex: Int?

    private let wikipediaService = WikipediaService()
    private let realRuntime = RealEPICRuntime()

    init() {
        availablePersonas = PersonaLoader.loadPersonas()
        persona = availablePersonas.first ?? PersonaLoader.fallbackPersona
        preferenceDrafts = persona.preferenceBlocks.map(\.preference)
        statusMessage = "PrefWiki persona \(persona.personaIndex) preset loaded."
    }

    /// True when either live EPIC indexing ran OR a pre-indexed persona was loaded.
    var indexReady: Bool { runtimeFootprint != nil || personaLoaded }

    var stats: PipelineStats {
        let existingBytes = runtimeFootprint?.existingTotalBytes ?? existingEntries.reduce(0) { $0 + $1.approximateBytes }
        let epicBytes = runtimeFootprint?.epicTotalBytes ?? epicEntries.reduce(0) { $0 + $1.approximateBytes }
        return PipelineStats(
            chunkCount: chunks.count,
            existingEntryCount: existingEntries.count,
            epicEntryCount: epicEntries.count,
            existingBytes: existingBytes,
            epicBytes: epicBytes,
            coarseCount: coarseCandidates.count,
            fineKeptChunkCount: Set(epicEntries.map(\.chunk.id)).count,
            fineRejectedChunkCount: fineEvaluations.filter { !$0.isKept }.count
        )
    }

    func searchWikipedia() {
        Task { await performSearch() }
    }

    func applyPreferenceDrafts() {
        let cleanedPreferences = preferenceDrafts
            .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty }

        persona = PersonaPreset(
            personaIndex: persona.personaIndex,
            preferenceBlocks: cleanedPreferences.map {
                PreferenceBlock(preference: $0, queries: [])
            }
        )
        preferenceDrafts = cleanedPreferences
        resetMemory()
        statusMessage = "\(cleanedPreferences.count) preferences set for indexing."
    }

    func selectPersonaPreset(index: Int) {
        guard let preset = availablePersonas.first(where: { $0.personaIndex == index }) else { return }
        setPersonaPreset(preset, status: "PrefWiki persona \(preset.personaIndex) preset loaded.")
    }

    func resetPreferenceDraftsToSelectedPersona() {
        let preset = availablePersonas.first(where: { $0.personaIndex == persona.personaIndex }) ?? PersonaLoader.loadDefaultPersona()
        setPersonaPreset(preset, status: "PrefWiki persona \(preset.personaIndex) preset restored.")
    }

    func resetPreferenceDraftsToPersonaZero() {
        let preset = availablePersonas.first(where: { $0.personaIndex == 0 }) ?? PersonaLoader.loadDefaultPersona()
        setPersonaPreset(preset, status: "PrefWiki persona 0 preset restored.")
    }

    private func setPersonaPreset(_ preset: PersonaPreset, status: String) {
        persona = preset
        preferenceDrafts = preset.preferenceBlocks.map(\.preference)
        resetMemory()
        statusMessage = status
    }

    func addPreferenceDraft() {
        preferenceDrafts.append("")
    }

    func removePreferenceDraft(at offsets: IndexSet) {
        for index in offsets.sorted(by: >) {
            guard preferenceDrafts.indices.contains(index) else { continue }
            preferenceDrafts.remove(at: index)
        }
    }

    func runFullPipeline() {
        Task {
            await performSearch()
            guard let first = searchResults.first else { return }
            await fetchArticle(first)
            runExistingRAG()
            await runEPICPipeline()
        }
    }

    func fetchArticle(_ result: WikipediaResult) {
        Task { await fetchArticle(result) }
    }

    func selectArticleForComparison(_ result: WikipediaResult) {
        Task {
            await fetchArticle(result)
            if selectedArticle != nil {
                runExistingRAG()
            }
        }
    }

    func loadArticleForComparison(_ result: WikipediaResult) async -> Bool {
        await fetchArticle(result)
        guard selectedArticle != nil else { return false }
        runExistingRAG()
        return true
    }

    func useSampleArticle() {
        Task {
            ingest(article: SampleArticles.automobile)
            runExistingRAG()
            await runEPICPipeline()
        }
    }

    func loadSampleForComparison() {
        ingest(article: SampleArticles.automobile)
        runExistingRAG()
        statusMessage = "Sample article ready for chunking."
    }

    func runExistingRAG() {
        existingEntries = EPICIndexer(threshold: coarseThreshold).existingRAGMemory(from: chunks)
        runtimeFootprint = nil
        runProgress = .idle
        chunkProgress = Dictionary(uniqueKeysWithValues: chunks.map { ($0.index, EPICChunkProgress.pending) })
        activeChunkIndex = chunks.first?.index
        statusMessage = "Existing RAG stored \(existingEntries.count) raw chunks; FAISS bytes are measured during EPIC."
    }

    func runEPIC() {
        Task {
            await runEPICPipeline()
        }
    }

    func runEPICAndWait() async {
        await runEPICPipeline()
    }

    func rebuildEPICForThresholdChange() {
        guard !chunks.isEmpty else { return }
        coarseCandidates = []
        fineEvaluations = []
        epicEntries = []
        runtimeFootprint = nil
        runProgress = .idle
        chunkProgress = Dictionary(uniqueKeysWithValues: chunks.map { ($0.index, EPICChunkProgress.pending) })
        activeChunkIndex = chunks.first?.index
        statusMessage = "Threshold set to \(String(format: "%.2f", coarseThreshold)); press Run EPIC to rebuild with Contriever + Llama."
    }

    func resetMemory() {
        existingEntries = []
        coarseCandidates = []
        fineEvaluations = []
        epicEntries = []
        runtimeFootprint = nil
        runProgress = .idle
        chunkProgress = Dictionary(uniqueKeysWithValues: chunks.map { ($0.index, EPICChunkProgress.pending) })
        activeChunkIndex = chunks.first?.index
        statusMessage = "Memory cleared; extracted chunks remain available."
    }

    private func runEPICPipeline() async {
        guard !chunks.isEmpty else {
            statusMessage = "Extract a Wikipedia page before running EPIC."
            return
        }

        errorMessage = nil
        isRunningEPIC = true
        prepareProgress()
        statusMessage = "Starting real-time EPIC indexing..."
        defer { isRunningEPIC = false }

        do {
            let result = try await realRuntime.runStreaming(
                chunks: chunks,
                persona: persona,
                threshold: coarseThreshold
            ) { [weak self] event in
                guard let self else { return }
                await self.apply(event)
            }
            apply(result)
            if existingEntries.isEmpty {
                existingEntries = EPICIndexer(threshold: coarseThreshold).existingRAGMemory(from: chunks)
            }
            runProgress = EPICRunProgress(
                phase: .completed,
                message: "EPIC completed.",
                fraction: 1,
                processedChunks: chunks.count,
                totalChunks: chunks.count,
                completedFine: fineEvaluations.count,
                totalFine: coarseCandidates.count
            )
            activeChunkIndex = chunks.last?.index
            statusMessage = "EPIC kept \(epicEntries.count) instruction-item pairs from \(coarseCandidates.count) coarse candidates."
        } catch {
            errorMessage = error.localizedDescription
            runProgress = EPICRunProgress(
                phase: .failed,
                message: error.localizedDescription,
                fraction: runProgress.fraction,
                processedChunks: runProgress.processedChunks,
                totalChunks: runProgress.totalChunks,
                completedFine: runProgress.completedFine,
                totalFine: runProgress.totalFine
            )
            statusMessage = "Real EPIC runtime failed."
        }
    }

    private func performSearch() async {
        errorMessage = nil
        isLoading = true
        defer { isLoading = false }

        do {
            searchResults = try await wikipediaService.search(query: searchText)
            if searchResults.isEmpty {
                statusMessage = "No Wikipedia results found."
            } else {
                statusMessage = "Found \(searchResults.count) Wikipedia pages."
            }
        } catch {
            errorMessage = error.localizedDescription
            statusMessage = "Wikipedia search failed; sample article is available."
        }
    }

    private func fetchArticle(_ result: WikipediaResult) async {
        errorMessage = nil
        isLoading = true
        defer { isLoading = false }

        do {
            let article = try await wikipediaService.fetchArticle(pageID: result.pageID)
            ingest(article: article)
            statusMessage = "Extracted and chunked \(article.title)."
        } catch {
            errorMessage = error.localizedDescription
            statusMessage = "Article extraction failed; sample article is available."
        }
    }

    private func ingest(article: WikiArticle) {
        selectedArticle = article
        chunks = TextChunker.chunk(article: article)
        existingEntries = []
        coarseCandidates = []
        fineEvaluations = []
        epicEntries = []
        runtimeFootprint = nil
        runProgress = .idle
        chunkProgress = Dictionary(uniqueKeysWithValues: chunks.map { ($0.index, EPICChunkProgress.pending) })
        activeChunkIndex = chunks.first?.index
    }

    private func apply(_ result: RealEPICResult) {
        runtimeFootprint = result.runtime
        let chunkByIndex = Dictionary(uniqueKeysWithValues: chunks.map { ($0.index, $0) })

        coarseCandidates = result.coarseCandidates.compactMap {
            mapCoarseCandidate($0, chunkByIndex: chunkByIndex)
        }
        fineEvaluations = result.fineEvaluations.compactMap {
            mapFineEvaluation($0, chunkByIndex: chunkByIndex)
        }

        epicEntries = fineEvaluations.flatMap(\.keptEntries)
        refreshFinalChunkProgress()
    }

    private func apply(_ event: RuntimeProgressEvent) {
        switch event.event {
        case "started":
            activeChunkIndex = chunks.first?.index
            updateProgress(
                phase: .preparing,
                message: "Preparing \(event.totalChunks ?? chunks.count) chunks for vector indexing.",
                fraction: 0.02,
                processedChunks: 0,
                totalChunks: event.totalChunks ?? chunks.count,
                completedFine: 0,
                totalFine: 0
            )

        case "embedding_started":
            chunks.forEach {
                chunkProgress[$0.index] = EPICChunkProgress(
                    state: .embedding,
                    detail: "Embedding",
                    score: nil
                )
            }
            updateProgress(
                phase: .embedding,
                message: "Embedding chunks with facebook/contriever.",
                fraction: 0.08,
                processedChunks: 0,
                totalChunks: event.totalChunks ?? chunks.count
            )

        case "embedding_progress":
            let processed = event.processedChunks ?? runProgress.processedChunks
            let total = max(event.totalChunks ?? runProgress.totalChunks, 1)
            focusChunk(atVisualPosition: processed)
            updateProgress(
                phase: .embedding,
                message: "Embedding chunks \(processed)/\(total).",
                fraction: 0.08 + (Double(processed) / Double(total)) * 0.18,
                processedChunks: processed,
                totalChunks: total
            )

        case "preference_embedding_started":
            updateProgress(
                phase: .embedding,
                message: "Encoding \(event.totalPreferences ?? persona.preferenceBlocks.count) user preferences.",
                fraction: 0.27
            )

        case "embedding_complete":
            chunks.forEach {
                chunkProgress[$0.index] = EPICChunkProgress(
                    state: .pending,
                    detail: "Embedded",
                    score: nil
                )
            }
            updateProgress(
                phase: .embedding,
                message: "Embeddings ready; building FAISS IndexFlatIP.",
                fraction: 0.30,
                processedChunks: chunks.count,
                totalChunks: chunks.count
            )

        case "existing_indexed":
            updateProgress(
                phase: .coarseFiltering,
                message: "Existing RAG FAISS index measured.",
                fraction: 0.34
            )

        case "coarse_started":
            updateProgress(
                phase: .chunkVerification,
                message: "Streaming each chunk through coarse filtering and fine verification.",
                fraction: 0.36,
                processedChunks: 0,
                totalChunks: event.totalChunks ?? chunks.count
            )

        case "coarse_candidate":
            let chunkIndex = event.chunkIndex
            if let chunkIndex {
                activeChunkIndex = chunkIndex
            }
            if let runtimeCandidate = event.coarseCandidate {
                let chunkByIndex = Dictionary(uniqueKeysWithValues: chunks.map { ($0.index, $0) })
                if let candidate = mapCoarseCandidate(runtimeCandidate, chunkByIndex: chunkByIndex) {
                    upsert(candidate)
                    chunkProgress[candidate.chunk.index] = EPICChunkProgress(
                        state: .coarseCandidate,
                        detail: "Coarse match",
                        score: candidate.topScore
                    )
                }
            } else if let chunkIndex {
                chunkProgress[chunkIndex] = EPICChunkProgress(
                    state: .coarseCandidate,
                    detail: "Coarse match",
                    score: nil
                )
            }
            updateCoarseProgress(event)

        case "coarse_filtered":
            if let chunkIndex = event.chunkIndex {
                activeChunkIndex = chunkIndex
                chunkProgress[chunkIndex] = EPICChunkProgress(
                    state: .filteredOut,
                    detail: "Below tau",
                    score: nil
                )
            }
            updateCoarseProgress(event)

        case "coarse_complete":
            let candidateCount = event.candidateCount ?? coarseCandidates.count
            updateProgress(
                phase: .chunkVerification,
                message: "Chunk-by-chunk verification found \(candidateCount) coarse candidates.",
                fraction: max(runProgress.fraction, 0.90),
                processedChunks: chunks.count,
                totalChunks: chunks.count,
                completedFine: fineEvaluations.count,
                totalFine: event.totalFine ?? candidateCount
            )

        case "fine_started":
            updateProgress(
                phase: .chunkVerification,
                message: "Starting Llama preference-aligned fine verification.",
                fraction: max(runProgress.fraction, event.totalFine == 0 ? 0.88 : 0.60),
                completedFine: 0,
                totalFine: event.totalFine ?? coarseCandidates.count
            )

        case "fine_chunk_started":
            if let chunkIndex = event.chunkIndex {
                activeChunkIndex = chunkIndex
                chunkProgress[chunkIndex] = EPICChunkProgress(
                    state: .fineVerifying,
                    detail: "LLM verifying",
                    score: chunkProgress[chunkIndex]?.score
                )
            }
            updateFineProgress(event, messagePrefix: "Fine verifying")

        case "fine_chunk_finished":
            let chunkByIndex = Dictionary(uniqueKeysWithValues: chunks.map { ($0.index, $0) })
            if let runtimeEvaluation = event.fineEvaluation,
               let evaluation = mapFineEvaluation(runtimeEvaluation, chunkByIndex: chunkByIndex) {
                activeChunkIndex = evaluation.chunk.index
                upsert(evaluation)
                epicEntries = fineEvaluations.flatMap(\.keptEntries)
                chunkProgress[evaluation.chunk.index] = EPICChunkProgress(
                    state: evaluation.isKept ? .fineKeep : .fineDiscard,
                    detail: evaluation.isKept ? "\(evaluation.keptEntries.count) instruction(s)" : "LLM discarded",
                    score: chunkProgress[evaluation.chunk.index]?.score
                )
            }
            updateFineProgress(event, messagePrefix: "Fine verified")

        case "fine_complete":
            updateProgress(
                phase: .instructionIndexing,
                message: "Fine verification complete; indexing instructions.",
                fraction: 0.92,
                completedFine: event.completedFine ?? fineEvaluations.count,
                totalFine: event.totalFine ?? coarseCandidates.count
            )

        case "instruction_index_started":
            updateProgress(
                phase: .instructionIndexing,
                message: "Embedding generated instructions for EPIC memory.",
                fraction: 0.94
            )

        case "instruction_index_complete":
            updateProgress(
                phase: .instructionIndexing,
                message: "Instruction index built with \(event.instructionCount ?? epicEntries.count) entries.",
                fraction: 0.98
            )

        case "complete":
            if let result = event.result {
                apply(result)
            }
            activeChunkIndex = chunks.last?.index
            updateProgress(
                phase: .completed,
                message: "EPIC completed.",
                fraction: 1,
                processedChunks: chunks.count,
                totalChunks: chunks.count,
                completedFine: fineEvaluations.count,
                totalFine: coarseCandidates.count
            )

        case "error":
            errorMessage = event.error
            updateProgress(
                phase: .failed,
                message: event.error ?? "EPIC runtime failed.",
                fraction: runProgress.fraction
            )

        default:
            break
        }
    }

    private func mapPreferenceMatch(_ match: RuntimePreferenceMatch) -> PreferenceMatch {
        PreferenceMatch(
            preferenceIndex: match.preferenceIndex,
            preference: match.preference,
            kind: PreferenceKind(rawValue: match.kind) ?? PreferenceKind.inferred(from: match.preference),
            score: match.score,
            matchedTerms: match.matchedTerms
        )
    }

    private func mapMemoryEntry(_ entry: RuntimeEPICMemoryEntry, chunkByIndex: [Int: DocumentChunk]) -> EPICMemoryEntry? {
        guard let chunk = chunkByIndex[entry.chunkIndex] else { return nil }
        return EPICMemoryEntry(
            chunk: chunk,
            preferenceIndex: entry.preferenceIndex,
            preference: entry.preference,
            kind: PreferenceKind(rawValue: entry.kind) ?? PreferenceKind.inferred(from: entry.preference),
            instruction: entry.instruction,
            rationale: entry.rationale,
            matchedTerms: entry.matchedTerms
        )
    }

    private func prepareProgress() {
        coarseCandidates = []
        fineEvaluations = []
        epicEntries = []
        runtimeFootprint = nil
        chunkProgress = Dictionary(uniqueKeysWithValues: chunks.map { ($0.index, EPICChunkProgress.pending) })
        activeChunkIndex = chunks.first?.index
        runProgress = EPICRunProgress(
            phase: .preparing,
            message: "Preparing indexing run.",
            fraction: 0,
            processedChunks: 0,
            totalChunks: chunks.count,
            completedFine: 0,
            totalFine: 0
        )
    }

    private func updateProgress(
        phase: EPICRunPhase,
        message: String,
        fraction: Double? = nil,
        processedChunks: Int? = nil,
        totalChunks: Int? = nil,
        completedFine: Int? = nil,
        totalFine: Int? = nil
    ) {
        let nextFraction = min(max(fraction ?? runProgress.fraction, 0), 1)
        runProgress = EPICRunProgress(
            phase: phase,
            message: message,
            fraction: nextFraction,
            processedChunks: processedChunks ?? runProgress.processedChunks,
            totalChunks: totalChunks ?? runProgress.totalChunks,
            completedFine: completedFine ?? runProgress.completedFine,
            totalFine: totalFine ?? runProgress.totalFine
        )
        statusMessage = message
    }

    private func updateCoarseProgress(_ event: RuntimeProgressEvent) {
        let processed = event.processedChunks ?? runProgress.processedChunks
        let total = max(event.totalChunks ?? runProgress.totalChunks, 1)
        updateProgress(
            phase: .chunkVerification,
            message: "Routing chunk \(processed)/\(total) through EPIC.",
            fraction: chunkVerificationFraction(processed: processed, total: total),
            processedChunks: processed,
            totalChunks: total
        )
    }

    private func updateFineProgress(_ event: RuntimeProgressEvent, messagePrefix: String) {
        let completed = event.completedFine ?? runProgress.completedFine
        let candidateTotal = event.totalFine ?? runProgress.totalFine
        let chunkLabel = event.chunkIndex.map { " chunk \($0)" } ?? ""
        let processed = event.processedChunks ?? runProgress.processedChunks
        let totalChunks = max(event.totalChunks ?? runProgress.totalChunks, 1)
        let fraction = event.processedChunks == nil
            ? 0.60 + (Double(completed) / Double(max(candidateTotal, 1))) * 0.30
            : chunkVerificationFraction(processed: processed, total: totalChunks)
        updateProgress(
            phase: .chunkVerification,
            message: "\(messagePrefix)\(chunkLabel) · chunk \(processed)/\(totalChunks), candidates \(completed)/\(max(candidateTotal, 0)).",
            fraction: max(runProgress.fraction, fraction),
            processedChunks: processed,
            totalChunks: totalChunks,
            completedFine: completed,
            totalFine: candidateTotal
        )
    }

    private func chunkVerificationFraction(processed: Int, total: Int) -> Double {
        0.36 + (Double(processed) / Double(max(total, 1))) * 0.54
    }

    private func focusChunk(atVisualPosition position: Int) {
        guard !chunks.isEmpty else {
            activeChunkIndex = nil
            return
        }
        let boundedIndex = min(max(position - 1, 0), chunks.count - 1)
        activeChunkIndex = chunks[boundedIndex].index
    }

    private func mapCoarseCandidate(
        _ candidate: RuntimeCoarseCandidate,
        chunkByIndex: [Int: DocumentChunk]
    ) -> CoarseCandidate? {
        guard let chunk = chunkByIndex[candidate.chunkIndex] else { return nil }
        return CoarseCandidate(
            chunk: chunk,
            matches: candidate.matches.map(mapPreferenceMatch)
        )
    }

    private func mapFineEvaluation(
        _ evaluation: RuntimeFineEvaluation,
        chunkByIndex: [Int: DocumentChunk]
    ) -> FineEvaluation? {
        guard let chunk = chunkByIndex[evaluation.chunkIndex] else { return nil }
        return FineEvaluation(
            chunk: chunk,
            candidateMatches: evaluation.candidateMatches.map(mapPreferenceMatch),
            keptEntries: evaluation.keptEntries.compactMap { mapMemoryEntry($0, chunkByIndex: chunkByIndex) },
            rejectedReason: evaluation.rejectedReason
        )
    }

    private func upsert(_ candidate: CoarseCandidate) {
        if let index = coarseCandidates.firstIndex(where: { $0.chunk.index == candidate.chunk.index }) {
            coarseCandidates[index] = candidate
        } else {
            coarseCandidates.append(candidate)
        }
        coarseCandidates.sort { $0.chunk.index < $1.chunk.index }
    }

    private func upsert(_ evaluation: FineEvaluation) {
        if let index = fineEvaluations.firstIndex(where: { $0.chunk.index == evaluation.chunk.index }) {
            fineEvaluations[index] = evaluation
        } else {
            fineEvaluations.append(evaluation)
        }
        fineEvaluations.sort { $0.chunk.index < $1.chunk.index }
    }

    // ── Pre-indexed persona loading ───────────────────────────────────────

    @Published var isLoadingPersona = false
    @Published var personaLoadError: String?
    @Published var personaLoaded = false   // true once /load_persona succeeds

    func loadPersonaIndex() {
        Task { await performLoadPersona() }
    }

    private func performLoadPersona() async {
        isLoadingPersona = true
        personaLoadError = nil
        personaLoaded = false
        defer { isLoadingPersona = false }
        do {
            let result = try await generationRuntime.loadPersona(index: persona.personaIndex)
            epicIndexBytes = result.epicIndexBytes
            ragIndexBytes = result.ragIndexBytes
            epicEntryCount = result.epicEntries
            ragChunkCount = result.ragChunks
            personaLoaded = true
        } catch {
            personaLoadError = error.localizedDescription
        }
    }

    // ── Generation ────────────────────────────────────────────────────────

    func runGenerate() {
        guard !generationQuestion.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return }
        Task { await performGenerate() }
    }

    private func performGenerate() async {
        generationError = nil
        evaluationResult = nil
        evaluationError = nil
        epicResponseText = ""
        ragResponseText = ""
        epicRetrievedDocs = []
        ragRetrievedDocs = []
        topPreference = ""
        generationComplete = false
        isGenerating = true
        defer { isGenerating = false }

        do {
            let (epicResp, ragResp, epicDocs, ragDocs, pref) = try await generationRuntime.generate(
                question: generationQuestion,
                topK: 5
            ) { [weak self] event in
                guard let self else { return }
                await MainActor.run {
                    switch event.event {
                    case "retrieved":
                        self.epicRetrievedDocs = event.epicDocs ?? []
                        self.ragRetrievedDocs = event.ragDocs ?? []
                        self.epicRetrLatencyMs = event.epicRetrMs
                        self.ragRetrLatencyMs = event.ragRetrMs
                        self.epicIndexBytes = event.epicIndexBytes
                        self.ragIndexBytes = event.ragIndexBytes
                        self.epicEntryCount = event.epicEntries
                        self.ragChunkCount = event.ragChunks
                    case "epic_token":
                        self.epicResponseText += event.text ?? ""
                    case "rag_token":
                        self.ragResponseText += event.text ?? ""
                    default:
                        break
                    }
                }
            }
            epicResponseText = epicResp
            ragResponseText = ragResp
            epicRetrievedDocs = epicDocs
            ragRetrievedDocs = ragDocs
            topPreference = pref
            generationComplete = true
        } catch {
            generationError = error.localizedDescription
        }
    }

    func runEvaluate() {
        guard generationComplete,
              !epicResponseText.isEmpty,
              !ragResponseText.isEmpty,
              !topPreference.isEmpty else { return }
        Task { await performEvaluate() }
    }

    private func performEvaluate() async {
        evaluationError = nil
        isEvaluating = true
        defer { isEvaluating = false }
        do {
            evaluationResult = try await generationRuntime.evaluate(
                question: generationQuestion,
                preference: topPreference,
                epicResponse: epicResponseText,
                ragResponse: ragResponseText
            )
        } catch {
            evaluationError = error.localizedDescription
        }
    }

    private func refreshFinalChunkProgress() {
        let keptChunkIndexes = Set(epicEntries.map(\.chunk.index))
        let rejectedChunkIndexes = Set(fineEvaluations.filter { !$0.isKept }.map(\.chunk.index))
        let coarseChunkIndexes = Set(coarseCandidates.map(\.chunk.index))

        for chunk in chunks {
            if keptChunkIndexes.contains(chunk.index) {
                let instructionCount = epicEntries.filter { $0.chunk.index == chunk.index }.count
                chunkProgress[chunk.index] = EPICChunkProgress(
                    state: .fineKeep,
                    detail: "\(instructionCount) instruction(s)",
                    score: coarseCandidates.first(where: { $0.chunk.index == chunk.index })?.topScore
                )
            } else if rejectedChunkIndexes.contains(chunk.index) {
                chunkProgress[chunk.index] = EPICChunkProgress(
                    state: .fineDiscard,
                    detail: "LLM discarded",
                    score: coarseCandidates.first(where: { $0.chunk.index == chunk.index })?.topScore
                )
            } else if coarseChunkIndexes.contains(chunk.index) {
                chunkProgress[chunk.index] = EPICChunkProgress(
                    state: .coarseCandidate,
                    detail: "Coarse match",
                    score: coarseCandidates.first(where: { $0.chunk.index == chunk.index })?.topScore
                )
            } else {
                chunkProgress[chunk.index] = EPICChunkProgress(
                    state: .filteredOut,
                    detail: "Below tau",
                    score: nil
                )
            }
        }
    }
}
