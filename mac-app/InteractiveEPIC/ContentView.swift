import AppKit
import SwiftUI

/// Top-level demo mode, chosen on the landing screen.
private enum DemoMode {
    case indexing   // live EPIC indexing walkthrough on a Wikipedia article
    case retrieval  // pre-indexed corpus → retrieval breakdown → generation → evaluation
}

private enum DemoStage: Int, CaseIterable {
    case modeSelect
    // Indexing-mode stages
    case preferences
    case wikipedia
    case chunking
    case comparison
    // Retrieval-mode stages
    case personaSelect
    case retrieval
    case generation
    case evaluation
    case results

    /// Stages shown as pills in the header, depending on the active mode.
    static func flow(for mode: DemoMode?) -> [DemoStage] {
        switch mode {
        case nil: [.modeSelect]
        case .indexing: [.preferences, .wikipedia, .chunking, .comparison, .results]
        // Generation/Evaluation stay implemented but hidden from this flow —
        // re-add .generation/.evaluation here to surface them again.
        case .retrieval: [.personaSelect, .retrieval, .generation, .evaluation]
        }
    }

    var title: String {
        switch self {
        case .modeSelect: "Start"
        case .preferences: "Preferences"
        case .wikipedia: "Wikipedia"
        case .chunking: "Chunking"
        case .comparison: "Indexing"
        case .personaSelect: "Persona"
        case .retrieval: "Retrieval"
        case .generation: "Generation"
        case .evaluation: "Evaluation"
        case .results: "Results"
        }
    }

    var subtitle: String {
        switch self {
        case .modeSelect: "Choose a demo"
        case .preferences: "Persona setup"
        case .wikipedia: "Search and extract"
        case .chunking: "Document chunks"
        case .comparison: "RAG vs EPIC"
        case .personaSelect: "Load pre-indexed memory"
        case .retrieval: "Query steering, EPIC vs RAG"
        case .generation: "EPIC vs Plain RAG"
        case .evaluation: "Preference following"
        case .results: "Memory outcome"
        }
    }

    var symbol: String {
        switch self {
        case .modeSelect: "house"
        case .preferences: "person.text.rectangle"
        case .wikipedia: "globe"
        case .chunking: "scissors"
        case .comparison: "square.split.2x1"
        case .personaSelect: "person.crop.circle"
        case .retrieval: "arrow.triangle.2.circlepath.circle"
        case .generation: "bubble.left.and.bubble.right"
        case .evaluation: "checkmark.seal"
        case .results: "chart.bar.xaxis"
        }
    }
}

struct ContentView: View {
    @StateObject private var demo = EPICDemoViewModel()
    @State private var stage: DemoStage = .modeSelect
    @State private var mode: DemoMode?
    @State private var selectedResultChunk: DocumentChunk?
    @State private var animatedChunkCount = 0
    @State private var chunkingReplayToken = 0
    @FocusState private var focusedPreferenceIndex: Int?
    @FocusState private var isPreferenceContinueFocused: Bool

    var body: some View {
        VStack(spacing: 0) {
            header
            Divider()

            Group {
                switch stage {
                case .modeSelect:
                    modeSelectScreen
                case .preferences:
                    preferencesScreen
                case .wikipedia:
                    wikipediaScreen
                case .chunking:
                    chunkingScreen
                case .comparison:
                    comparisonScreen
                case .personaSelect:
                    personaSelectScreen
                case .retrieval:
                    retrievalScreen
                case .generation:
                    generationScreen
                case .evaluation:
                    evaluationScreen
                case .results:
                    resultsScreen
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
        .frame(minWidth: 1440, minHeight: 920)
        .controlSize(.large)
        .font(.system(size: 15))
        .background(Color(nsColor: .windowBackgroundColor))
        .sheet(item: $selectedResultChunk) { chunk in
            ResultChunkDetailSheet(
                chunk: chunk,
                entries: resultEntries(for: chunk),
                candidate: resultCandidate(for: chunk),
                evaluation: resultEvaluation(for: chunk)
            )
        }
    }

    private var header: some View {
        HStack(spacing: 18) {
            VStack(alignment: .leading, spacing: 3) {
                HStack(spacing: 8) {
                    Text("Interactive EPIC")
                        .font(.system(size: 26, weight: .bold, design: .rounded))
                    if mode != nil {
                        Button {
                            withAnimation {
                                if mode == .retrieval {
                                    demo.resetRetrievalDemo()
                                }
                                mode = nil
                                stage = .modeSelect
                            }
                        } label: {
                            Label("Home", systemImage: "house")
                                .font(.caption)
                        }
                        .buttonStyle(.borderless)
                        .foregroundStyle(.secondary)
                    }
                }
            }

            Spacer(minLength: 16)

            HStack(spacing: 8) {
                ForEach(DemoStage.flow(for: mode), id: \.self) { item in
                    StagePill(stage: item, currentStage: stage)
                }
            }
        }
        .padding(.horizontal, 22)
        .padding(.top, 18)
        .padding(.bottom, 14)
    }

    // ── Mode select (landing) ────────────────────────────────────────────

    private var modeSelectScreen: some View {
        VStack(spacing: 44) {
            Spacer()

            VStack(spacing: 18) {
                Text("ICML 2026")
                    .font(.title3.weight(.bold))
                    .foregroundStyle(.white)
                    .padding(.horizontal, 20)
                    .padding(.vertical, 9)
                    .background(Color.teal)
                    .clipShape(Capsule())

                Text("From Volume to Value")
                    .font(.system(size: 68, weight: .bold, design: .rounded))
                Text("Preference-Aligned Memory Construction for On-Device RAG")
                    .font(.system(size: 30, weight: .medium))
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
                Text("Changmin Lee · Jaemin Kim · Taesik Gong")
                    .font(.title2.weight(.medium))
                    .foregroundStyle(.secondary)
            }
            .multilineTextAlignment(.center)
            .frame(maxWidth: 1100)

            Text("Choose which part of the pipeline to demo")
                .font(.system(size: 26, weight: .semibold))
                .foregroundStyle(.secondary)

            HStack(spacing: 32) {
                ModeCard(
                    symbol: "scissors",
                    title: "Indexing Demo",
                    detail: "Walk through EPIC indexing live: pick a persona, search Wikipedia, chunk a document, run coarse + fine filtering, and watch the EPIC memory get built step by step.",
                    color: .teal
                ) {
                    withAnimation {
                        mode = .indexing
                        stage = .preferences
                    }
                }

                ModeCard(
                    symbol: "arrow.triangle.2.circlepath.circle",
                    title: "Retrieval Demo",
                    detail: "Load a persona's pre-built EPIC memory over the full corpus, compare it against Plain RAG — memory footprint, retrieval latency, query steering — then generate and evaluate responses.",
                    color: .orange
                ) {
                    withAnimation {
                        mode = .retrieval
                        stage = .personaSelect
                    }
                }
            }
            .frame(maxWidth: 1120)

            Spacer()
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .padding(40)
    }

    // ── Persona select (retrieval mode) ─────────────────────────────────

    private var personaSelectScreen: some View {
        VStack(alignment: .leading, spacing: 18) {
            ScreenTitle(
                symbol: "person.crop.circle",
                title: "Select a Persona",
                subtitle: "Load that persona's pre-indexed EPIC memory over the full corpus."
            )

            GuideBanner(text: demo.personaLoaded
                ? "Loaded! Click \"Continue to Retrieval\" below to compare EPIC vs Plain RAG."
                : "Pick a persona below, then click \"Load Persona\" to load its memory.")

            PersonaPresetSelector(
                selectedPersonaIndex: Binding(
                    get: { demo.persona.personaIndex },
                    set: {
                        demo.selectPersonaPreset(index: $0)
                        demo.personaLoaded = false
                    }
                ),
                personas: demo.availablePersonas
            )

            VStack(alignment: .leading, spacing: 14) {
                HStack(spacing: 12) {
                    if demo.isLoadingPersona {
                        ProgressView("Loading persona \(demo.persona.personaIndex)'s memory…")
                    } else {
                        Button {
                            demo.loadPersonaIndex()
                        } label: {
                            Label(demo.personaLoaded ? "Reload Persona \(demo.persona.personaIndex)" : "Load Persona \(demo.persona.personaIndex)",
                                  systemImage: "arrow.down.circle.fill")
                        }
                        .buttonStyle(.borderedProminent)
                        .tint(.teal)
                    }

                    if demo.personaLoaded {
                        Button {
                            withAnimation { stage = .retrieval }
                        } label: {
                            Label("Continue to Retrieval", systemImage: "arrow.right")
                        }
                        .buttonStyle(.borderedProminent)
                    }
                }

                if let err = demo.personaLoadError {
                    ErrorBanner(message: err)
                }

                if demo.personaLoaded {
                    MemoryReductionComparison(
                        epicEntryCount: demo.epicEntryCount ?? 0,
                        epicBytes: demo.epicIndexBytes ?? 0,
                        ragChunkCount: demo.ragChunkCount ?? 0,
                        ragBytes: demo.ragIndexBytes ?? 0
                    )
                }
            }
            .padding(18)
            .background(Color.teal.opacity(0.06))
            .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))

            Spacer()
        }
        .padding(26)
    }

    // ── Retrieval breakdown (retrieval mode) ────────────────────────────

    private var retrievalScreen: some View {
        VStack(alignment: .leading, spacing: 18) {
            HStack(alignment: .top) {
                ScreenTitle(
                    symbol: "arrow.triangle.2.circlepath.circle",
                    title: "Retrieval Breakdown",
                    subtitle: "EPIC instruction-steered retrieval vs Plain RAG"
                )
                Spacer()
                Button { withAnimation { stage = .personaSelect } } label: {
                    Label("Persona", systemImage: "arrow.left")
                }
                Button {
                    withAnimation { stage = .generation }
                } label: {
                    Label("Continue to Generation", systemImage: "arrow.right")
                }
                .buttonStyle(.borderedProminent)
                .disabled(!demo.personaLoaded)
            }

            GuideBanner(text: "Type a question below, then click \"Run Retrieval\" to compare EPIC vs Plain RAG.", color: .orange)

            // Memory footprint comparison
            MemoryReductionComparison(
                epicEntryCount: demo.epicEntryCount ?? 0,
                epicBytes: demo.epicIndexBytes ?? 0,
                ragChunkCount: demo.ragChunkCount ?? 0,
                ragBytes: demo.ragIndexBytes ?? 0
            )

            // Query input
            HStack(spacing: 10) {
                TextField("Ask a question to see how retrieval differs…", text: $demo.retrievalQuestion)
                    .textFieldStyle(.roundedBorder)
                    .font(.title3)
                    .onSubmit { demo.runRetrievalDemo() }
                Button {
                    demo.runRetrievalDemo()
                } label: {
                    Label(demo.isRetrieving ? "Retrieving…" : "Run Retrieval", systemImage: "magnifyingglass.circle.fill")
                }
                .buttonStyle(.borderedProminent)
                .disabled(demo.isRetrieving || demo.retrievalQuestion.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || !demo.personaLoaded)
            }

            if !demo.personaLoaded {
                Label("Load a persona first.", systemImage: "exclamationmark.triangle")
                    .font(.caption)
                    .foregroundStyle(.orange)
            }

            if let err = demo.retrievalError {
                ErrorBanner(message: err)
            }

            // Animated step tracker
            if demo.isRetrieving || demo.retrievalStep != .idle {
                RetrievalStepTracker(currentStep: demo.retrievalStep)
            }

            // Results: latency breakdown + doc comparison
            if demo.retrievalStep == .done, let result = demo.retrievalResult {
                LatencyBreakdownBar(
                    embedMs: result.embedMs,
                    steerMs: result.steerMs,
                    matchedPreference: result.matchedPreference,
                    epicSearchMs: result.epicSearchMs,
                    ragSearchMs: result.ragSearchMs
                )

                HStack(alignment: .top, spacing: 16) {
                    RetrievalResultPanel(
                        title: "EPIC-RAG",
                        color: .teal,
                        symbol: "bolt.horizontal.circle.fill",
                        latencyMs: result.epicRetrMs,
                        docs: result.epicDocs,
                        isEPIC: true
                    )
                    RetrievalResultPanel(
                        title: "Plain RAG",
                        color: .orange,
                        symbol: "tray.full",
                        latencyMs: result.ragRetrMs,
                        docs: result.ragDocs,
                        isEPIC: false
                    )
                }
                .frame(maxHeight: .infinity)
            } else if !demo.isRetrieving {
                EmptyState(
                    symbol: "magnifyingglass",
                    title: "Run a retrieval query",
                    detail: "Type a question and press Run Retrieval to see how EPIC steers toward preference-aligned docs versus Plain RAG's raw similarity search."
                )
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
        }
        .padding(26)
    }

    private var preferencesScreen: some View {
        HStack(spacing: 0) {
            VStack(alignment: .leading, spacing: 18) {
                ScreenTitle(
                    symbol: "person.crop.circle.badge.checkmark",
                    title: "User Preferences",
                    subtitle: "Choose a PrefWiki persona, then edit preferences."
                )

                GuideBanner(text: "Pick a persona, review its preferences, then click \"Continue.\"")

                PersonaPresetSelector(
                    selectedPersonaIndex: Binding(
                        get: { demo.persona.personaIndex },
                        set: {
                            demo.selectPersonaPreset(index: $0)
                            focusedPreferenceIndex = nil
                            isPreferenceContinueFocused = true
                        }
                    ),
                    personas: demo.availablePersonas
                )

                VStack(alignment: .leading, spacing: 12) {
                    PreferenceStatTile(title: "Persona", value: "\(demo.persona.personaIndex)", detail: "selected preset")
                    PreferenceStatTile(title: "Active Preferences", value: "\(demo.preferenceDrafts.filter { !$0.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }.count)", detail: "used at indexing time")
                }

                Spacer()

                VStack(spacing: 10) {
                    Button {
                        demo.addPreferenceDraft()
                    } label: {
                        Label("Add Preference", systemImage: "plus")
                            .frame(maxWidth: .infinity)
                    }

                    Button {
                        demo.resetPreferenceDraftsToSelectedPersona()
                    } label: {
                        Label("Reset Persona \(demo.persona.personaIndex)", systemImage: "arrow.counterclockwise")
                            .frame(maxWidth: .infinity)
                    }

                    Button {
                        demo.applyPreferenceDrafts()
                        stage = .wikipedia
                    } label: {
                        Label("Continue", systemImage: "arrow.right")
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.borderedProminent)
                    .disabled(demo.preferenceDrafts.allSatisfy { $0.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty })
                    .focused($isPreferenceContinueFocused)
                }
            }
            .padding(26)
            .frame(width: 340)
            .background(Color(nsColor: .controlBackgroundColor).opacity(0.55))

            Divider()

            ScrollView {
                LazyVStack(spacing: 8) {
                    ForEach(Array(demo.preferenceDrafts.indices), id: \.self) { index in
                        PreferenceEditorRow(
                            index: index,
                            text: Binding(
                                get: {
                                    guard demo.preferenceDrafts.indices.contains(index) else { return "" }
                                    return demo.preferenceDrafts[index]
                                },
                                set: { newValue in
                                    guard demo.preferenceDrafts.indices.contains(index) else { return }
                                    demo.preferenceDrafts[index] = newValue
                                }
                            ),
                            canDelete: demo.preferenceDrafts.count > 1,
                            focusedPreferenceIndex: $focusedPreferenceIndex,
                            deleteAction: {
                                demo.removePreferenceDraft(at: IndexSet(integer: index))
                            }
                        )
                    }
                }
                .padding(18)
            }
        }
        .onAppear {
            focusedPreferenceIndex = nil
            isPreferenceContinueFocused = true
            DispatchQueue.main.async {
                focusedPreferenceIndex = nil
                isPreferenceContinueFocused = true
            }
        }
    }

    private var wikipediaScreen: some View {
        VStack(alignment: .leading, spacing: 18) {
            HStack(alignment: .top) {
                ScreenTitle(
                    symbol: "globe",
                    title: "Wikipedia Search",
                    subtitle: "\(demo.persona.preferenceBlocks.count) preferences will guide EPIC indexing."
                )

                Spacer()

                Button {
                    stage = .preferences
                } label: {
                    Label("Preferences", systemImage: "arrow.left")
                }
            }

            GuideBanner(text: "Search a topic, then click a result below to extract it.")

            HStack(spacing: 10) {
                TextField("Search Wikipedia", text: $demo.searchText)
                    .textFieldStyle(.roundedBorder)
                    .font(.title3)
                    .onSubmit {
                        demo.searchWikipedia()
                    }

                Button {
                    demo.searchWikipedia()
                } label: {
                    Label("Search", systemImage: "magnifyingglass")
                }
                .buttonStyle(.borderedProminent)
            }

            if let errorMessage = demo.errorMessage {
                ErrorBanner(message: errorMessage)
            }

            if demo.isLoading {
                LoadingPanel(title: "Searching Wikipedia")
            } else if demo.searchResults.isEmpty {
                EmptyState(symbol: "doc.text.magnifyingglass", title: "No page selected", detail: "Search for a topic to extract a Wikipedia page.")
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                ScrollView {
                    LazyVGrid(columns: [GridItem(.adaptive(minimum: 310), spacing: 12)], spacing: 12) {
                        ForEach(demo.searchResults) { result in
                            WikipediaResultTile(result: result) {
                                Task {
                                    if await demo.loadArticleForComparison(result) {
                                        animatedChunkCount = 0
                                        stage = .chunking
                                    }
                                }
                            }
                        }
                    }
                    .padding(.vertical, 2)
                }
            }
        }
        .padding(26)
    }

    private var chunkingScreen: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack(alignment: .top) {
                ScreenTitle(
                    symbol: "scissors",
                    title: "Document Chunking",
                    subtitle: demo.selectedArticle?.title ?? "No document selected"
                )

                Spacer()

                Button {
                    stage = .wikipedia
                } label: {
                    Label("Wikipedia", systemImage: "arrow.left")
                }

                Button {
                    animatedChunkCount = 0
                    chunkingReplayToken += 1
                } label: {
                    Label("Replay", systemImage: "arrow.counterclockwise")
                }
                .disabled(demo.chunks.isEmpty)

                Button {
                    stage = .comparison
                } label: {
                    Label("Start Indexing", systemImage: "arrow.right")
                }
                .buttonStyle(.borderedProminent)
                .disabled(demo.chunks.isEmpty)
            }

            GuideBanner(text: "Watch the document get split into chunks, then click \"Start Indexing.\"")

            if let article = demo.selectedArticle {
                HStack(spacing: 12) {
                    ChunkingMetricTile(title: "Document Words", value: "\(article.wordCount)", detail: article.source.rawValue, symbol: "doc.text", tint: .blue)
                    ChunkingMetricTile(title: "Target Size", value: "100", detail: "approx. words", symbol: "text.word.spacing", tint: .teal)
                    ChunkingMetricTile(title: "Safeguard", value: "Sentence", detail: "never split mid-sentence", symbol: "text.quote", tint: .purple)
                    ChunkingMetricTile(title: "Chunks", value: "\(animatedChunkCount)/\(demo.chunks.count)", detail: "ready for indexing", symbol: "square.stack.3d.up", tint: .orange)
                }

                HStack(alignment: .top, spacing: 14) {
                    RawArticlePanel(article: article)
                    ChunkingChunkGrid(chunks: demo.chunks, visibleCount: animatedChunkCount)
                }
            } else {
                EmptyState(symbol: "doc.text.magnifyingglass", title: "No document selected", detail: "Choose a Wikipedia page before chunking.")
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
        }
        .padding(26)
        .task(id: chunkingAnimationKey) {
            await runChunkingAnimation()
        }
    }

    private var chunkingAnimationKey: String {
        "\(stage.rawValue)-\(demo.selectedArticle?.id ?? -1)-\(demo.chunks.count)-\(chunkingReplayToken)"
    }

    @MainActor
    private func runChunkingAnimation() async {
        guard stage == .chunking, !demo.chunks.isEmpty else {
            animatedChunkCount = 0
            return
        }

        animatedChunkCount = 0
        let delay: UInt64 = demo.chunks.count > 80 ? 20_000_000 : 34_000_000
        for count in 1...demo.chunks.count {
            try? await Task.sleep(nanoseconds: delay)
            if Task.isCancelled { return }
            withAnimation(.spring(response: 0.30, dampingFraction: 0.82)) {
                animatedChunkCount = count
            }
        }
    }

    private var comparisonScreen: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack(alignment: .top) {
                ScreenTitle(
                    symbol: "square.split.2x1",
                    title: demo.selectedArticle?.title ?? "Indexing Comparison",
                    subtitle: "\(demo.chunks.count) chunks from \(demo.selectedArticle?.source.rawValue ?? "document")"
                )

                Spacer()

                if demo.isRunningEPIC {
                    ProgressView()
                        .controlSize(.small)
                }

                Button {
                    stage = demo.selectedArticle == nil ? .wikipedia : .chunking
                } label: {
                    Label("Back", systemImage: "arrow.left")
                }
                .disabled(demo.isRunningEPIC)

                Button {
                    Task {
                        await demo.runEPICAndWait()
                        if demo.runtimeFootprint != nil {
                            try? await Task.sleep(nanoseconds: 1_200_000_000)
                            stage = .results
                        }
                    }
                } label: {
                    Label(demo.runtimeFootprint == nil ? "Start EPIC" : "Run Again", systemImage: "bolt.fill")
                }
                .buttonStyle(.borderedProminent)
                .disabled(demo.isRunningEPIC || demo.chunks.isEmpty)

                Button {
                    stage = .results
                } label: {
                    Label("Results", systemImage: "chart.bar.xaxis")
                }
                .disabled(demo.runtimeFootprint == nil)
            }

            GuideBanner(text: demo.runtimeFootprint == nil
                ? "Click \"Start EPIC\" to run coarse + fine filtering and build the memory."
                : "Indexing complete — click \"Results\" to see what got kept and why.")

            RuntimeSettingsBar(footprint: demo.runtimeFootprint, threshold: demo.coarseThreshold)

            if let errorMessage = demo.errorMessage {
                ErrorBanner(message: errorMessage)
            }

            ChunkAnimationArena(demo: demo)
                .frame(maxHeight: .infinity, alignment: .topLeading)
        }
        .padding(26)
    }

    private var resultsScreen: some View {
        VStack(alignment: .leading, spacing: 18) {
            HStack(alignment: .top) {
                ScreenTitle(
                    symbol: "chart.bar.xaxis",
                    title: "Indexing Result",
                    subtitle: demo.selectedArticle?.title ?? "No article"
                )

                Spacer()

                Button {
                    stage = .comparison
                } label: {
                    Label("Comparison", systemImage: "arrow.left")
                }

                Button {
                    demo.resetMemory()
                    stage = .wikipedia
                } label: {
                    Label("New Document", systemImage: "doc.badge.plus")
                }
                .buttonStyle(.borderedProminent)
            }

            HStack(spacing: 12) {
                ResultMetricTile(title: "Existing RAG Memory", value: demo.stats.existingBytes.memoryString, detail: "\(demo.stats.existingEntryCount) raw chunks", tint: .orange, symbol: "externaldrive.fill")
                ResultMetricTile(title: "EPIC Memory", value: demo.stats.epicBytes.memoryString, detail: "\(demo.stats.epicEntryCount) instruction-item pairs", tint: .teal, symbol: "bolt.horizontal.circle.fill")
                ResultMetricTile(title: "Memory Delta", value: demo.stats.reductionText, detail: "\(demo.stats.savedBytes.memoryString) not stored", tint: .green, symbol: "chart.line.downtrend.xyaxis")
                ResultMetricTile(title: "Fine Rejected", value: "\(demo.stats.fineRejectedChunkCount)", detail: "coarse candidates", tint: .red, symbol: "xmark.seal")
            }

            RuntimeSettingsBar(footprint: demo.runtimeFootprint, threshold: demo.coarseThreshold)

            VStack(alignment: .leading, spacing: 10) {
                HStack(alignment: .firstTextBaseline) {
                    Text("Chunk Memory Cards")
                        .font(.headline)
                    Text("click a card for raw document, instruction, and relevant preference")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    Spacer()
                    Text("\(demo.chunks.count) chunks")
                        .font(.caption.monospacedDigit().weight(.bold))
                        .foregroundStyle(.secondary)
                }

                ScrollView {
                    LazyVGrid(columns: resultGridColumns, alignment: .leading, spacing: 12) {
                        ForEach(demo.chunks) { chunk in
                            ResultChunkCard(
                                chunk: chunk,
                                entries: resultEntries(for: chunk),
                                candidate: resultCandidate(for: chunk),
                                evaluation: resultEvaluation(for: chunk)
                            ) {
                                selectedResultChunk = chunk
                            }
                        }
                    }
                    .padding(.vertical, 2)
                }
                .frame(minHeight: 280)
            }
        }
        .padding(26)
    }

    private var resultGridColumns: [GridItem] {
        [GridItem(.adaptive(minimum: 238, maximum: 310), spacing: 12)]
    }

    private func resultEntries(for chunk: DocumentChunk) -> [EPICMemoryEntry] {
        demo.epicEntries.filter { $0.chunk.index == chunk.index }
    }

    private func resultCandidate(for chunk: DocumentChunk) -> CoarseCandidate? {
        demo.coarseCandidates.first { $0.chunk.index == chunk.index }
    }

    private func resultEvaluation(for chunk: DocumentChunk) -> FineEvaluation? {
        demo.fineEvaluations.first { $0.chunk.index == chunk.index }
    }
}

private struct StagePill: View {
    let stage: DemoStage
    let currentStage: DemoStage

    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: stage.symbol)
                .font(.body.weight(.bold))
            VStack(alignment: .leading, spacing: 1) {
                Text(stage.title)
                    .font(.body.weight(.bold))
                Text(stage.subtitle)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        }
        .foregroundStyle(isCurrent ? .teal : .secondary)
        .padding(.horizontal, 13)
        .padding(.vertical, 9)
        .background(isCurrent ? .teal.opacity(0.12) : Color(nsColor: .controlBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .stroke(isCurrent ? .teal.opacity(0.28) : Color.primary.opacity(0.08))
        )
    }

    private var isCurrent: Bool {
        stage == currentStage
    }
}

private struct ScreenTitle: View {
    let symbol: String
    let title: String
    let subtitle: String

    var body: some View {
        HStack(spacing: 14) {
            Image(systemName: symbol)
                .font(.system(size: 24, weight: .semibold))
                .foregroundStyle(.teal)
                .frame(width: 56, height: 56)
                .background(.teal.opacity(0.12))
                .clipShape(Circle())

            VStack(alignment: .leading, spacing: 4) {
                Text(title)
                    .font(.system(size: 36, weight: .bold, design: .rounded))
                    .lineLimit(1)
                    .minimumScaleFactor(0.78)
                Text(subtitle)
                    .font(.title3)
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
            }
        }
    }
}

// ── Guide banner: tells the audience what to do on this screen ─────────────

private struct GuideBanner: View {
    let text: String
    var color: Color = .teal

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: "hand.point.right.fill")
                .font(.title3.weight(.semibold))
            Text(text)
                .font(.title3.weight(.semibold))
                .fixedSize(horizontal: false, vertical: true)
        }
        .foregroundStyle(color)
        .padding(.horizontal, 18)
        .padding(.vertical, 12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(color.opacity(0.10))
        .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
    }
}

private struct PreferenceStatTile: View {
    let title: String
    let value: String
    let detail: String

    var body: some View {
        VStack(alignment: .leading, spacing: 5) {
            Text(value)
                .font(.system(size: 28, weight: .bold, design: .rounded))
            Text(title)
                .font(.caption.weight(.semibold))
            Text(detail)
                .font(.caption2)
                .foregroundStyle(.secondary)
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color(nsColor: .textBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
    }
}

private struct PersonaPresetSelector: View {
    @Binding var selectedPersonaIndex: Int
    let personas: [PersonaPreset]

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Label("PrefWiki Persona", systemImage: "person.2.crop.square.stack")
                    .font(.caption.weight(.bold))
                    .foregroundStyle(.secondary)
                Spacer()
                Text("\(personas.count) presets")
                    .font(.caption2.monospacedDigit().weight(.semibold))
                    .foregroundStyle(.secondary)
            }

            Picker("PrefWiki Persona", selection: $selectedPersonaIndex) {
                ForEach(personas) { preset in
                    Text("Persona \(preset.personaIndex) — \(PersonaDescriptions.short(for: preset.personaIndex)) · \(preset.preferenceBlocks.count) prefs")
                        .tag(preset.personaIndex)
                }
            }
            .labelsHidden()
            .pickerStyle(.menu)
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color(nsColor: .textBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .stroke(Color.primary.opacity(0.08))
        )
    }
}

private struct PreferenceEditorRow: View {
    let index: Int
    @Binding var text: String
    let canDelete: Bool
    @FocusState.Binding var focusedPreferenceIndex: Int?
    let deleteAction: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text("Preference \(index + 1)")
                    .font(.subheadline.weight(.bold))
                    .foregroundStyle(.secondary)
                Spacer()
                Button(action: deleteAction) {
                    Image(systemName: "trash")
                        .font(.body)
                }
                .buttonStyle(.borderless)
                .disabled(!canDelete)
            }

            TextField("Preference", text: $text, axis: .vertical)
                .font(.system(size: 18, weight: .medium))
                .textFieldStyle(.plain)
                .focused($focusedPreferenceIndex, equals: index)
                .lineLimit(1...2)
                .frame(minHeight: 32, maxHeight: 56, alignment: .center)
                .padding(.horizontal, 7)
                .padding(.vertical, 3)
                .background(Color(nsColor: .controlBackgroundColor).opacity(0.75))
                .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 8)
        .background(Color(nsColor: .textBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .stroke(Color.primary.opacity(0.08))
        )
    }
}

private struct WikipediaResultTile: View {
    let result: WikipediaResult
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            VStack(alignment: .leading, spacing: 10) {
                HStack(alignment: .firstTextBaseline) {
                    Text(result.title)
                        .font(.headline)
                        .lineLimit(1)
                    Spacer()
                    Text(result.wordCount > 0 ? "\(result.wordCount) words" : "page")
                        .font(.caption2.monospacedDigit())
                        .foregroundStyle(.secondary)
                }

                Text(result.snippet.isEmpty ? "Wikipedia page" : result.snippet)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .lineLimit(4)
                    .frame(minHeight: 58, alignment: .top)

                HStack {
                    Spacer()
                    Image(systemName: "arrow.right.circle.fill")
                        .foregroundStyle(.teal)
                }
            }
            .padding(14)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Color(nsColor: .textBackgroundColor))
            .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: 8, style: .continuous)
                    .stroke(Color.primary.opacity(0.08))
            )
        }
        .buttonStyle(.plain)
    }
}

private struct ChunkingMetricTile: View {
    let title: String
    let value: String
    let detail: String
    let symbol: String
    let tint: Color

    var body: some View {
        HStack(spacing: 10) {
            Image(systemName: symbol)
                .foregroundStyle(tint)
                .frame(width: 30, height: 30)
                .background(tint.opacity(0.12))
                .clipShape(Circle())

            VStack(alignment: .leading, spacing: 2) {
                Text(value)
                    .font(.title3.monospacedDigit().weight(.bold))
                    .lineLimit(1)
                Text(title)
                    .font(.caption.weight(.semibold))
                    .lineLimit(1)
                Text(detail)
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
            }
            Spacer(minLength: 0)
        }
        .padding(12)
        .frame(maxWidth: .infinity, minHeight: 78, alignment: .leading)
        .background(Color(nsColor: .textBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .stroke(tint.opacity(0.12))
        )
    }
}

private struct RawArticlePanel: View {
    let article: WikiArticle

    var body: some View {
        VStack(alignment: .leading, spacing: 11) {
            HStack(spacing: 8) {
                Image(systemName: "doc.plaintext")
                    .foregroundStyle(.blue)
                Text("Selected Wikipedia Extract")
                    .font(.headline)
                Spacer()
                Text("\(article.wordCount) words")
                    .font(.caption.monospacedDigit().weight(.semibold))
                    .foregroundStyle(.secondary)
            }

            ScrollView {
                Text(article.extract)
                    .font(.body)
                    .lineSpacing(4)
                    .textSelection(.enabled)
                    .frame(maxWidth: .infinity, alignment: .topLeading)
            }
            .frame(maxHeight: .infinity)
        }
        .padding(14)
        .frame(maxWidth: .infinity, minHeight: 480, alignment: .topLeading)
        .background(Color(nsColor: .textBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .stroke(Color.primary.opacity(0.08))
        )
    }
}

private struct ChunkingChunkGrid: View {
    let chunks: [DocumentChunk]
    let visibleCount: Int

    private var visibleChunks: [DocumentChunk] {
        Array(chunks.prefix(max(0, min(visibleCount, chunks.count))))
    }

    private var progress: Double {
        guard !chunks.isEmpty else { return 0 }
        return Double(visibleChunks.count) / Double(chunks.count)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 11) {
            HStack(spacing: 8) {
                Image(systemName: "square.stack.3d.up")
                    .foregroundStyle(.orange)
                Text("Chunk Stream")
                    .font(.headline)
                Spacer()
                Text("\(visibleChunks.count) / \(chunks.count)")
                    .font(.caption.monospacedDigit().weight(.semibold))
                    .foregroundStyle(.secondary)
            }

            ProgressView(value: progress)
                .tint(.orange)

            if visibleChunks.isEmpty {
                VStack(spacing: 8) {
                    ProgressView()
                        .controlSize(.small)
                    Text("Splitting document into sentence-preserving chunks")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                ScrollViewReader { proxy in
                    ScrollView {
                        LazyVGrid(columns: [GridItem(.adaptive(minimum: 142, maximum: 190), spacing: 8)], spacing: 8) {
                            ForEach(visibleChunks) { chunk in
                                ChunkingChunkCard(chunk: chunk)
                                    .id(chunk.index)
                                    .transition(.asymmetric(
                                        insertion: .scale(scale: 0.88).combined(with: .opacity),
                                        removal: .opacity
                                    ))
                            }
                        }
                        .padding(.vertical, 2)
                    }
                    .onChange(of: visibleCount) { _, _ in
                        guard let last = visibleChunks.last else { return }
                        withAnimation(.easeOut(duration: 0.22)) {
                            proxy.scrollTo(last.index, anchor: .bottom)
                        }
                    }
                }
            }
        }
        .padding(14)
        .frame(maxWidth: .infinity, minHeight: 480, alignment: .topLeading)
        .background(Color(nsColor: .controlBackgroundColor).opacity(0.68))
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .stroke(Color.orange.opacity(0.14))
        )
        .animation(.spring(response: 0.30, dampingFraction: 0.82), value: visibleCount)
    }
}

private struct ChunkingChunkCard: View {
    let chunk: DocumentChunk

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(alignment: .firstTextBaseline) {
                Text("\(chunk.index)")
                    .font(.caption.monospacedDigit().weight(.black))
                    .foregroundStyle(.white)
                    .frame(width: 25, height: 25)
                    .background(.orange)
                    .clipShape(Circle())
                Spacer()
                Text("\(chunk.wordCount) words")
                    .font(.caption2.monospacedDigit().weight(.semibold))
                    .foregroundStyle(.secondary)
            }

            Text(chunk.preview)
                .font(.caption)
                .lineLimit(5)
                .frame(maxWidth: .infinity, minHeight: 78, alignment: .topLeading)
        }
        .padding(10)
        .frame(maxWidth: .infinity, minHeight: 126, alignment: .topLeading)
        .background(Color(nsColor: .textBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .stroke(Color.orange.opacity(0.18))
        )
    }
}

private struct RuntimeSettingsBar: View {
    let footprint: RealEPICFootprint?
    let threshold: Double

    private let columns = [GridItem(.adaptive(minimum: 220, maximum: 320), spacing: 10)]

    var body: some View {
        LazyVGrid(columns: columns, alignment: .leading, spacing: 10) {
            RuntimeBadge(symbol: "point.3.connected.trianglepath.dotted", title: "Embedding", value: footprint?.embeddingModel ?? "facebook/contriever")
            RuntimeBadge(symbol: "number", title: "Threshold", value: String(format: "tau %.2f", footprint?.threshold ?? threshold))
            RuntimeBadge(symbol: "square.stack.3d.up", title: "Vector index", value: footprint?.vectorIndex ?? "FAISS IndexFlatIP")
            RuntimeBadge(symbol: "cpu", title: "Fine verifier", value: footprint?.llm ?? "Llama-3.1-8B via vLLM")
        }
    }
}

private struct RuntimeBadge: View {
    let symbol: String
    let title: String
    let value: String

    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: symbol)
                .foregroundStyle(.teal)
                .frame(width: 24, height: 24)
                .background(.teal.opacity(0.10))
                .clipShape(Circle())
            VStack(alignment: .leading, spacing: 1) {
                Text(title)
                    .font(.caption2.weight(.semibold))
                    .foregroundStyle(.secondary)
                Text(value)
                    .font(.caption.weight(.semibold))
                    .lineLimit(1)
                    .minimumScaleFactor(0.72)
            }
            Spacer(minLength: 0)
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 8)
        .frame(maxWidth: .infinity, minHeight: 48)
        .background(Color(nsColor: .textBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .stroke(Color.primary.opacity(0.08))
        )
    }
}

private struct PipelineSummaryTile: View {
    let title: String
    let value: String
    let detail: String
    let tint: Color
    let symbol: String

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: symbol)
                .font(.headline)
                .foregroundStyle(tint)
                .frame(width: 34, height: 34)
                .background(tint.opacity(0.12))
                .clipShape(Circle())
            VStack(alignment: .leading, spacing: 2) {
                Text(value)
                    .font(.title2.weight(.bold))
                Text(title)
                    .font(.caption.weight(.semibold))
                Text(detail)
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
            }
            Spacer()
        }
        .padding(13)
        .frame(maxWidth: .infinity, minHeight: 92)
        .background(Color(nsColor: .textBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
    }
}

private struct IndexingBattleBoard: View {
    @ObservedObject var demo: EPICDemoViewModel

    var body: some View {
        HStack(spacing: 12) {
            BattleSidePanel(
                title: "Existing RAG",
                subtitle: "Indiscriminate indexing",
                symbol: "tray.full",
                tint: .orange,
                primaryValue: "\(demo.existingEntries.count)",
                primaryLabel: "raw chunks stored",
                memoryValue: demo.stats.existingBytes.memoryString,
                progress: existingProgress,
                progressLabel: "\(demo.existingEntries.count)/\(demo.chunks.count) chunks",
                notes: [
                    "Stores every extracted chunk",
                    "No preference check",
                    "No usage instruction"
                ]
            )

            VStack(spacing: 8) {
                Text("VS")
                    .font(.headline.weight(.black))
                    .foregroundStyle(.white)
                    .frame(width: 44, height: 44)
                    .background(Color.primary.opacity(0.88))
                    .clipShape(Circle())

                Image(systemName: "arrow.left.and.right")
                    .font(.caption.weight(.bold))
                    .foregroundStyle(.secondary)
            }
            .frame(width: 54)

            BattleSidePanel(
                title: "EPIC",
                subtitle: "Preference-aligned indexing",
                symbol: "bolt.horizontal.circle.fill",
                tint: .teal,
                primaryValue: "\(demo.epicEntries.count)",
                primaryLabel: "instruction-item pairs",
                memoryValue: demo.stats.epicBytes == 0 ? "Pending" : demo.stats.epicBytes.memoryString,
                progress: epicProgress,
                progressLabel: epicProgressLabel,
                notes: [
                    "\(demo.coarseCandidates.count) coarse candidates",
                    "\(Set(demo.epicEntries.map(\.chunk.id)).count) LLM-kept chunks",
                    "Stores preference + instruction"
                ]
            )
        }
    }

    private var existingProgress: Double {
        guard !demo.chunks.isEmpty else { return 0 }
        return Double(demo.existingEntries.count) / Double(demo.chunks.count)
    }

    private var epicProgress: Double {
        guard !demo.chunks.isEmpty else { return 0 }
        let keptChunkCount = Set(demo.epicEntries.map(\.chunk.id)).count
        if demo.runtimeFootprint == nil, keptChunkCount == 0 {
            return demo.runProgress.fraction * 0.25
        }
        return Double(keptChunkCount) / Double(demo.chunks.count)
    }

    private var epicProgressLabel: String {
        let keptChunkCount = Set(demo.epicEntries.map(\.chunk.id)).count
        if demo.runtimeFootprint == nil, keptChunkCount == 0 {
            return demo.isRunningEPIC ? "filtering in progress" : "waiting for EPIC"
        }
        return "\(keptChunkCount)/\(demo.chunks.count) chunks kept"
    }
}

private struct BattleSidePanel: View {
    let title: String
    let subtitle: String
    let symbol: String
    let tint: Color
    let primaryValue: String
    let primaryLabel: String
    let memoryValue: String
    let progress: Double
    let progressLabel: String
    let notes: [String]

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 10) {
                Image(systemName: symbol)
                    .font(.title3.weight(.semibold))
                    .foregroundStyle(tint)
                    .frame(width: 36, height: 36)
                    .background(tint.opacity(0.12))
                    .clipShape(Circle())

                VStack(alignment: .leading, spacing: 2) {
                    Text(title)
                        .font(.headline.weight(.bold))
                    Text(subtitle)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }

                Spacer()
            }

            HStack(alignment: .firstTextBaseline, spacing: 8) {
                Text(primaryValue)
                    .font(.system(size: 34, weight: .bold, design: .rounded))
                    .monospacedDigit()
                Text(primaryLabel)
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
                    .minimumScaleFactor(0.75)
            }

            VStack(alignment: .leading, spacing: 5) {
                ProgressView(value: min(max(progress, 0), 1))
                    .tint(tint)
                HStack {
                    Text(progressLabel)
                    Spacer()
                    Text(memoryValue)
                        .fontWeight(.bold)
                }
                .font(.caption2.monospacedDigit())
                .foregroundStyle(.secondary)
            }

            HStack(spacing: 6) {
                ForEach(notes, id: \.self) { note in
                    BattleNote(label: note, tint: tint)
                }
            }
        }
        .padding(14)
        .frame(maxWidth: .infinity, minHeight: 170, alignment: .topLeading)
        .background(Color(nsColor: .textBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .stroke(tint.opacity(0.18))
        )
    }
}

private struct BattleNote: View {
    let label: String
    let tint: Color

    var body: some View {
        Text(label)
            .font(.caption2.weight(.semibold))
            .lineLimit(1)
            .minimumScaleFactor(0.68)
            .foregroundStyle(tint)
            .padding(.horizontal, 7)
            .padding(.vertical, 4)
            .frame(maxWidth: .infinity)
            .background(tint.opacity(0.10))
            .clipShape(Capsule())
    }
}

private struct ChunkAnimationArena: View {
    @ObservedObject var demo: EPICDemoViewModel

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            ChunkSpotlightCard(
                chunk: activeChunk,
                state: activeState,
                progress: activeProgress,
                existingCount: demo.existingEntries.count,
                epicKeptCount: epicKeptChunkCount
            )

            HStack(alignment: .top, spacing: 12) {
                ChunkTokenMap(
                    title: "Existing RAG memory",
                    subtitle: existingRAGSubtitle,
                    chunks: demo.chunks,
                    activeChunkIndex: isSharedEmbedding ? demo.activeChunkIndex : nil,
                    legendItems: existingRAGLegendItems,
                    tokenColor: { chunk in existingRAGTokenColor(for: chunk) },
                    tokenSymbol: { chunk in existingRAGTokenSymbol(for: chunk) },
                    tokenUsesPlainFill: { _ in false }
                )

                ChunkTokenMap(
                    title: "EPIC route",
                    subtitle: "preference-aligned indexing",
                    chunks: demo.chunks,
                    activeChunkIndex: demo.activeChunkIndex,
                    legendItems: [
                        ChunkTokenLegendItem(
                            label: "kept \(epicKeptChunkCount)",
                            symbol: "checkmark",
                            tint: .teal
                        ),
                        ChunkTokenLegendItem(
                            label: "coarse drop \(epicCoarseFilteredCount)",
                            symbol: "minus",
                            tint: .gray
                        ),
                        ChunkTokenLegendItem(
                            label: "fine drop \(epicFineRejectedCount)",
                            symbol: "xmark",
                            tint: .red
                        )
                    ],
                    tokenColor: { chunk in state(for: chunk).tint },
                    tokenSymbol: { chunk in state(for: chunk).compactSymbol },
                    tokenUsesPlainFill: { chunk in state(for: chunk) == .pending }
                )
            }
        }
        .padding(16)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .background(Color(nsColor: .controlBackgroundColor).opacity(0.65))
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
        .animation(.easeInOut(duration: 0.18), value: demo.chunkProgress)
    }

    private var activeChunk: DocumentChunk? {
        if let activeChunkIndex = demo.activeChunkIndex,
           let chunk = demo.chunks.first(where: { $0.index == activeChunkIndex }) {
            return chunk
        }
        return demo.chunks.first
    }

    private var activeProgress: EPICChunkProgress? {
        guard let activeChunk else { return nil }
        return demo.chunkProgress[activeChunk.index]
    }

    private var activeState: EPICChunkState {
        guard let activeProgress else { return .pending }
        return EPICChunkState(activeProgress.state)
    }

    private var isSharedEmbedding: Bool {
        demo.runProgress.phase == .embedding
    }

    private var existingRAGSubtitle: String {
        "indiscriminate indexing"
    }

    private var existingRAGLegendItems: [ChunkTokenLegendItem] {
        if isSharedEmbedding {
            return [
                ChunkTokenLegendItem(
                    label: "embedding \(demo.runProgress.processedChunks)/\(max(demo.runProgress.totalChunks, demo.chunks.count))",
                    symbol: "circle.dotted",
                    tint: .purple
                )
            ]
        }

        return [
            ChunkTokenLegendItem(
                label: "raw kept \(demo.existingEntries.count)",
                symbol: "checkmark",
                tint: .orange
            )
        ]
    }

    private func existingRAGTokenColor(for chunk: DocumentChunk) -> Color {
        guard isSharedEmbedding else { return .orange }
        if let progress = demo.chunkProgress[chunk.index], progress.state == .embedding {
            return .purple
        }
        return .secondary
    }

    private func existingRAGTokenSymbol(for chunk: DocumentChunk) -> String {
        guard isSharedEmbedding else { return "checkmark" }
        if let progress = demo.chunkProgress[chunk.index], progress.state == .embedding {
            return "circle.dotted"
        }
        return "clock"
    }

    private var existingDetail: String {
        guard let activeChunk else { return "waiting" }
        return "Chunk \(activeChunk.index) stored raw"
    }

    private var epicVerdict: String {
        switch activeState {
        case .pending:
            return "Waiting"
        case .embedding:
            return "Embedding"
        case .filteredOut:
            return "Discard"
        case .coarseOnly:
            return "Candidate"
        case .fineVerifying:
            return "Verifying"
        case .fineDiscard:
            return "Discard"
        case .fineKeep:
            return "Keep"
        }
    }

    private var epicDetail: String {
        switch activeState {
        case .pending:
            return "not checked yet"
        case .embedding:
            return "Contriever vector"
        case .filteredOut:
            return "below tau"
        case .coarseOnly:
            return activeProgress.flatMap(scoreText) ?? "coarse match"
        case .fineVerifying:
            return "vLLM checking"
        case .fineDiscard:
            return "not preference-aligned"
        case .fineKeep:
            return activeProgress?.detail ?? "instruction stored"
        }
    }

    private var epicKeptChunkCount: Int {
        Set(demo.epicEntries.map(\.chunk.index)).count
    }

    private var epicDiscardedChunkCount: Int {
        demo.chunkProgress.values.filter {
            $0.state == .filteredOut || $0.state == .fineDiscard
        }.count
    }

    private var epicCoarseFilteredCount: Int {
        demo.chunkProgress.values.filter { $0.state == .filteredOut }.count
    }

    private var epicFineRejectedCount: Int {
        demo.chunkProgress.values.filter { $0.state == .fineDiscard }.count
    }

    private func scoreText(_ progress: EPICChunkProgress) -> String? {
        guard let score = progress.score else { return nil }
        return "cosine \(String(format: "%.3f", score))"
    }

    private func state(for chunk: DocumentChunk) -> EPICChunkState {
        if let progress = demo.chunkProgress[chunk.index] {
            return EPICChunkState(progress.state)
        }
        if demo.runtimeFootprint == nil, demo.coarseCandidates.isEmpty, demo.epicEntries.isEmpty {
            return .pending
        }
        if demo.epicEntries.contains(where: { $0.chunk.id == chunk.id }) {
            return .fineKeep
        }
        if demo.fineEvaluations.contains(where: { $0.chunk.id == chunk.id && !$0.isKept }) {
            return .fineDiscard
        }
        if demo.coarseCandidates.contains(where: { $0.chunk.id == chunk.id }) {
            return .coarseOnly
        }
        return .filteredOut
    }
}

private struct ChunkDestinationPanel: View {
    let title: String
    let subtitle: String
    let verdict: String
    let detail: String
    let count: String
    let countLabel: String
    let symbol: String
    let tint: Color
    let isActive: Bool

    var body: some View {
        HStack(alignment: .center, spacing: 13) {
            HStack(spacing: 9) {
                Image(systemName: symbol)
                    .font(.headline.weight(.bold))
                    .foregroundStyle(tint)
                    .frame(width: 34, height: 34)
                    .background(tint.opacity(isActive ? 0.18 : 0.10))
                    .clipShape(Circle())
                VStack(alignment: .leading, spacing: 1) {
                    Text(title)
                        .font(.caption.weight(.bold))
                    Text(subtitle)
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }
                Spacer()
            }
            .frame(maxWidth: .infinity, alignment: .leading)

            VStack(alignment: .leading, spacing: 3) {
                Text(verdict)
                    .font(.system(size: 24, weight: .bold, design: .rounded))
                    .foregroundStyle(tint)
                    .lineLimit(1)
                    .minimumScaleFactor(0.76)

                Text(detail)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
                    .minimumScaleFactor(0.78)
            }
            .frame(maxWidth: .infinity, alignment: .leading)

            HStack(alignment: .firstTextBaseline, spacing: 5) {
                Text(count)
                    .font(.title2.weight(.bold))
                    .monospacedDigit()
                Text(countLabel)
                    .font(.caption2.weight(.semibold))
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
                    .minimumScaleFactor(0.72)
            }
            .frame(width: 130, alignment: .trailing)
        }
        .padding(14)
        .frame(maxWidth: .infinity, minHeight: 92, alignment: .leading)
        .background(Color(nsColor: .textBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .stroke(tint.opacity(isActive ? 0.30 : 0.10))
        )
    }
}

private struct ChunkSpotlightCard: View {
    let chunk: DocumentChunk?
    let state: EPICChunkState
    let progress: EPICChunkProgress?
    let existingCount: Int
    let epicKeptCount: Int

    var body: some View {
        VStack(alignment: .leading, spacing: 15) {
            HStack {
                Text(chunk.map { "Chunk \($0.index)" } ?? "Chunk")
                    .font(.title3.weight(.bold))
                Spacer()
                SelectionPill(label: state.label, symbol: state.symbol, tint: state.tint)
                    .frame(width: 148)
            }

            ScrollView(.vertical) {
                Text(chunkText)
                    .font(.callout)
                    .lineSpacing(3)
                    .lineLimit(nil)
                    .fixedSize(horizontal: false, vertical: true)
                    .frame(maxWidth: .infinity, alignment: .topLeading)
            }
            .frame(maxWidth: .infinity, minHeight: 92, maxHeight: 128, alignment: .topLeading)

            HStack(spacing: 10) {
                ChunkDecisionCard(
                    title: "Existing RAG",
                    verdict: existingRAGVerdict,
                    detail: existingRAGDetail,
                    store: existingRAGStore,
                    symbol: existingRAGSymbol,
                    tint: existingRAGTint
                )

                ChunkDecisionCard(
                    title: "EPIC decision",
                    verdict: state.decisionTitle,
                    detail: epicDecisionDetail,
                    store: state.storageText(keptCount: epicKeptCount, progress: progress),
                    symbol: state.symbol,
                    tint: state.tint
                )
            }
        }
        .padding(18)
        .frame(maxWidth: .infinity, minHeight: 316, alignment: .topLeading)
        .background(Color(nsColor: .textBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .stroke(state.tint.opacity(state == .pending ? 0.12 : 0.30))
        )
        .shadow(color: state.tint.opacity(state == .fineVerifying ? 0.22 : 0), radius: 10)
    }

    private var epicDecisionDetail: String {
        if let score = progress?.score {
            return "\(state.decisionDetail) · cosine \(String(format: "%.3f", score))"
        }
        if let detail = progress?.detail, state == .fineKeep || state == .fineDiscard {
            return "\(state.decisionDetail) · \(detail)"
        }
        return state.decisionDetail
    }

    private var chunkText: String {
        chunk?.text.collapsedWhitespace ?? "Select a Wikipedia document to begin."
    }

    private var existingRAGVerdict: String {
        state == .embedding ? "Embedding chunk" : "Keep raw chunk"
    }

    private var existingRAGDetail: String {
        if state == .embedding {
            return "Contriever is embedding this chunk."
        }
        return "Stores the raw chunk and vector without preference filtering."
    }

    private var existingRAGStore: String {
        "\(existingCount) raw chunks"
    }

    private var existingRAGSymbol: String {
        state == .embedding ? "point.3.connected.trianglepath.dotted" : "tray.full"
    }

    private var existingRAGTint: Color {
        state == .embedding ? .purple : .orange
    }

}

private struct ChunkDecisionCard: View {
    let title: String
    let verdict: String
    let detail: String
    let store: String
    let symbol: String
    let tint: Color

    var body: some View {
        HStack(alignment: .top, spacing: 10) {
            Image(systemName: symbol)
                .font(.headline.weight(.bold))
                .foregroundStyle(tint)
                .frame(width: 32, height: 32)
                .background(tint.opacity(0.13))
                .clipShape(Circle())

            VStack(alignment: .leading, spacing: 5) {
                HStack(alignment: .firstTextBaseline) {
                    Text(title)
                        .font(.caption.weight(.bold))
                        .foregroundStyle(.secondary)
                    Spacer(minLength: 8)
                    Text(store)
                        .font(.caption2.monospacedDigit().weight(.bold))
                        .foregroundStyle(tint)
                        .lineLimit(1)
                }

                Text(verdict)
                    .font(.headline.weight(.bold))
                    .foregroundStyle(tint)
                    .lineLimit(1)
                    .minimumScaleFactor(0.74)

                Text(detail)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .lineLimit(2)
                    .minimumScaleFactor(0.78)
            }
        }
        .padding(12)
        .frame(maxWidth: .infinity, minHeight: 94, alignment: .topLeading)
        .background(tint.opacity(0.07))
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .stroke(tint.opacity(0.18))
        )
    }
}

private struct ChunkTokenMap: View {
    let title: String
    let subtitle: String
    let chunks: [DocumentChunk]
    let activeChunkIndex: Int?
    let legendItems: [ChunkTokenLegendItem]
    let tokenColor: (DocumentChunk) -> Color
    let tokenSymbol: (DocumentChunk) -> String
    let tokenUsesPlainFill: (DocumentChunk) -> Bool

    private var gridColumns: [GridItem] {
        [GridItem(.adaptive(minimum: 20, maximum: 24), spacing: 5)]
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 9) {
            HStack {
                VStack(alignment: .leading, spacing: 1) {
                    Text(title)
                        .font(.caption.weight(.bold))
                    Text(subtitle)
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                        .minimumScaleFactor(0.78)
                }
                Spacer()
                Text("\(chunks.count)")
                    .font(.caption2.monospacedDigit().weight(.bold))
                    .foregroundStyle(.secondary)
            }

            if !legendItems.isEmpty {
                HStack(spacing: 12) {
                    ForEach(legendItems) { item in
                        ChunkTokenLegendPill(item: item)
                    }
                    Spacer(minLength: 0)
                }
            }

            LazyVGrid(columns: gridColumns, spacing: 5) {
                ForEach(chunks) { chunk in
                    ChunkToken(
                        chunk: chunk,
                        color: tokenColor(chunk),
                        symbol: tokenSymbol(chunk),
                        usesPlainFill: tokenUsesPlainFill(chunk),
                        isActive: chunk.index == activeChunkIndex
                    )
                }
            }
        }
        .padding(11)
        .frame(maxWidth: .infinity, minHeight: 132, alignment: .topLeading)
        .background(Color(nsColor: .textBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
    }
}

private struct ChunkTokenLegendItem: Identifiable {
    var id: String { label }
    let label: String
    let symbol: String
    let tint: Color
}

private struct ChunkTokenLegendPill: View {
    let item: ChunkTokenLegendItem

    var body: some View {
        HStack(spacing: 5) {
            Image(systemName: item.symbol)
                .font(.caption2.weight(.bold))
                .foregroundStyle(item.tint)
                .frame(width: 18, height: 18)
                .background(item.tint.opacity(0.14))
                .clipShape(RoundedRectangle(cornerRadius: 5, style: .continuous))

            Text(item.label)
                .font(.caption2.weight(.semibold))
                .foregroundStyle(.secondary)
                .lineLimit(1)
                .minimumScaleFactor(0.72)
        }
    }
}

private struct ChunkToken: View {
    let chunk: DocumentChunk
    let color: Color
    let symbol: String
    let usesPlainFill: Bool
    let isActive: Bool

    var body: some View {
        ZStack {
            RoundedRectangle(cornerRadius: 6, style: .continuous)
                .fill(usesPlainFill ? Color(nsColor: .textBackgroundColor) : color.opacity(isActive ? 0.24 : 0.13))
                .overlay(
                    RoundedRectangle(cornerRadius: 6, style: .continuous)
                        .stroke(color.opacity(isActive ? 0.72 : 0.24), lineWidth: isActive ? 1.6 : 1)
                )

            if isActive {
                Image(systemName: symbol)
                    .font(.caption2.weight(.black))
                    .foregroundStyle(color)
            } else {
                Text("\(chunk.index)")
                    .font(.caption2.monospacedDigit().weight(.bold))
                    .foregroundStyle(color)
            }
        }
        .frame(height: 22)
        .scaleEffect(isActive ? 1.16 : 1)
        .animation(.spring(response: 0.28, dampingFraction: 0.70), value: isActive)
    }
}

private struct EPICProgressPanel: View {
    let progress: EPICRunProgress
    let isRunning: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 10) {
                Image(systemName: progress.phase.symbolName)
                    .foregroundStyle(progress.phase.tint)
                    .frame(width: 28, height: 28)
                    .background(progress.phase.tint.opacity(0.12))
                    .clipShape(Circle())

                VStack(alignment: .leading, spacing: 2) {
                    Text(progress.phase.label)
                        .font(.caption.weight(.bold))
                    Text(progress.message)
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                }

                Spacer()

                Text("\(Int((progress.fraction * 100).rounded()))%")
                    .font(.caption.monospacedDigit().weight(.bold))
                    .foregroundStyle(progress.phase.tint)
            }

            ProgressView(value: progress.fraction)
                .tint(progress.phase.tint)

            HStack(spacing: 10) {
                ProgressCountPill(
                    title: "Coarse chunks",
                    value: "\(progress.processedChunks)/\(max(progress.totalChunks, 0))",
                    symbol: "line.3.horizontal.decrease.circle",
                    tint: .cyan
                )
                ProgressCountPill(
                    title: "Fine candidates",
                    value: "\(progress.completedFine)/\(max(progress.totalFine, 0))",
                    symbol: "checkmark.seal",
                    tint: .teal
                )
                ProgressCountPill(
                    title: "Runtime",
                    value: isRunning ? "Running" : progress.phase == .completed ? "Done" : "Ready",
                    symbol: isRunning ? "bolt.fill" : "circle",
                    tint: isRunning ? .blue : .secondary
                )
            }
        }
        .padding(12)
        .background(Color(nsColor: .textBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .stroke(progress.phase.tint.opacity(isRunning ? 0.25 : 0.08))
        )
    }
}

private struct ProgressCountPill: View {
    let title: String
    let value: String
    let symbol: String
    let tint: Color

    var body: some View {
        HStack(spacing: 7) {
            Image(systemName: symbol)
                .foregroundStyle(tint)
            Text(title)
                .foregroundStyle(.secondary)
            Text(value)
                .fontWeight(.bold)
                .foregroundStyle(.primary)
        }
        .font(.caption2)
        .padding(.horizontal, 9)
        .padding(.vertical, 5)
        .frame(maxWidth: .infinity)
        .background(Color(nsColor: .controlBackgroundColor).opacity(0.72))
        .clipShape(Capsule())
    }
}

private extension EPICRunPhase {
    var label: String {
        switch self {
        case .idle: "Ready"
        case .preparing: "Preparing"
        case .embedding: "Embedding"
        case .coarseFiltering: "Coarse Filtering"
        case .chunkVerification: "Chunk Verification"
        case .fineVerification: "Fine Verification"
        case .instructionIndexing: "Instruction Indexing"
        case .completed: "Completed"
        case .failed: "Failed"
        }
    }

    var symbolName: String {
        switch self {
        case .idle: "clock"
        case .preparing: "gearshape"
        case .embedding: "point.3.connected.trianglepath.dotted"
        case .coarseFiltering: "line.3.horizontal.decrease.circle"
        case .chunkVerification: "arrow.triangle.branch"
        case .fineVerification: "checkmark.seal"
        case .instructionIndexing: "square.stack.3d.up"
        case .completed: "checkmark.circle.fill"
        case .failed: "exclamationmark.triangle.fill"
        }
    }

    var tint: Color {
        switch self {
        case .idle: .secondary
        case .preparing: .blue
        case .embedding: .purple
        case .coarseFiltering: .cyan
        case .chunkVerification: .teal
        case .fineVerification: .teal
        case .instructionIndexing: .green
        case .completed: .green
        case .failed: .red
        }
    }
}

private struct ChunkComparisonList: View {
    @ObservedObject var demo: EPICDemoViewModel

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text("Chunk-by-Chunk Matchup")
                    .font(.headline)
                Spacer()
                Text("\(demo.chunks.count) chunks")
                    .font(.caption.monospacedDigit())
                    .foregroundStyle(.secondary)
            }

            HStack(spacing: 12) {
                Text("Document chunk")
                    .frame(maxWidth: .infinity, alignment: .leading)
                Text("Existing RAG")
                    .frame(width: 112)
                Text("EPIC")
                    .frame(width: 132)
            }
            .font(.caption2.weight(.bold))
            .foregroundStyle(.secondary)
            .padding(.horizontal, 12)

            ScrollView {
                LazyVStack(spacing: 10) {
                    ForEach(demo.chunks) { chunk in
                        ChunkComparisonRow(
                            chunk: chunk,
                            state: state(for: chunk),
                            progress: demo.chunkProgress[chunk.index]
                        )
                    }
                }
                .padding(.vertical, 2)
            }
        }
        .padding(14)
        .background(Color(nsColor: .controlBackgroundColor).opacity(0.65))
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
    }

    private func state(for chunk: DocumentChunk) -> EPICChunkState {
        if let progress = demo.chunkProgress[chunk.index] {
            return EPICChunkState(progress.state)
        }
        if demo.runtimeFootprint == nil, demo.coarseCandidates.isEmpty, demo.epicEntries.isEmpty {
            return .pending
        }
        if demo.epicEntries.contains(where: { $0.chunk.id == chunk.id }) {
            return .fineKeep
        }
        if demo.fineEvaluations.contains(where: { $0.chunk.id == chunk.id && !$0.isKept }) {
            return .fineDiscard
        }
        if demo.coarseCandidates.contains(where: { $0.chunk.id == chunk.id }) {
            return .coarseOnly
        }
        return .filteredOut
    }
}

private enum EPICChunkState {
    case pending
    case embedding
    case filteredOut
    case coarseOnly
    case fineVerifying
    case fineDiscard
    case fineKeep

    init(_ progressState: EPICChunkProgressState) {
        switch progressState {
        case .pending:
            self = .pending
        case .embedding:
            self = .embedding
        case .coarseCandidate:
            self = .coarseOnly
        case .filteredOut:
            self = .filteredOut
        case .fineVerifying:
            self = .fineVerifying
        case .fineDiscard:
            self = .fineDiscard
        case .fineKeep:
            self = .fineKeep
        }
    }

    var label: String {
        switch self {
        case .pending: "Waiting"
        case .embedding: "Embedding"
        case .filteredOut: "Filtered out"
        case .coarseOnly: "Coarse match"
        case .fineVerifying: "LLM verify"
        case .fineDiscard: "Discarded"
        case .fineKeep: "Fine Keep"
        }
    }

    var symbol: String {
        switch self {
        case .pending: "clock"
        case .embedding: "point.3.connected.trianglepath.dotted"
        case .filteredOut: "line.3.horizontal.decrease"
        case .coarseOnly: "scope"
        case .fineVerifying: "hourglass"
        case .fineDiscard: "xmark"
        case .fineKeep: "checkmark"
        }
    }

    var compactSymbol: String {
        switch self {
        case .pending: "clock"
        case .embedding: "circle.dotted"
        case .filteredOut: "minus"
        case .coarseOnly: "scope"
        case .fineVerifying: "hourglass"
        case .fineDiscard: "xmark"
        case .fineKeep: "checkmark"
        }
    }

    var tint: Color {
        switch self {
        case .pending: .secondary
        case .embedding: .purple
        case .filteredOut: .gray
        case .coarseOnly: .cyan
        case .fineVerifying: .blue
        case .fineDiscard: .red
        case .fineKeep: .teal
        }
    }

    var decisionTitle: String {
        switch self {
        case .pending:
            "Waiting"
        case .embedding:
            "Embedding chunk"
        case .filteredOut:
            "Coarse filtered"
        case .coarseOnly:
            "Coarse candidate"
        case .fineVerifying:
            "Fine verification"
        case .fineDiscard:
            "Fine rejected"
        case .fineKeep:
            "Kept as memory"
        }
    }

    var decisionDetail: String {
        switch self {
        case .pending:
            "EPIC has not evaluated this chunk yet."
        case .embedding:
            "Contriever is embedding this chunk."
        case .filteredOut:
            "Similarity stayed below tau, so this chunk is not sent to the LLM."
        case .coarseOnly:
            "Similarity passed tau; this chunk is queued for LLM verification."
        case .fineVerifying:
            "Llama is checking preference alignment and possible instructions."
        case .fineDiscard:
            "The LLM judged it not useful for the active preferences."
        case .fineKeep:
            "EPIC stores the preference-relevant chunk with an instruction."
        }
    }

    func storageText(keptCount: Int, progress: EPICChunkProgress?) -> String {
        switch self {
        case .pending, .embedding, .coarseOnly, .fineVerifying:
            return "evaluating"
        case .filteredOut, .fineDiscard:
            return "not stored"
        case .fineKeep:
            if let detail = progress?.detail, !detail.isEmpty {
                return detail
            }
            return "\(keptCount) kept"
        }
    }
}

private struct ChunkComparisonRow: View {
    let chunk: DocumentChunk
    let state: EPICChunkState
    let progress: EPICChunkProgress?

    var body: some View {
        HStack(alignment: .center, spacing: 12) {
            Text("\(chunk.index)")
                .font(.caption.monospacedDigit().weight(.bold))
                .foregroundStyle(.white)
                .frame(width: 28, height: 28)
                .background(.gray.opacity(0.85))
                .clipShape(Circle())

            VStack(alignment: .leading, spacing: 7) {
                HStack {
                    Text("\(chunk.wordCount) words")
                        .font(.caption2.monospacedDigit())
                        .foregroundStyle(.secondary)
                    Text(chunk.byteCount.memoryString)
                        .font(.caption2.monospacedDigit())
                        .foregroundStyle(.secondary)
                    Spacer()
                }

                Text(chunk.preview)
                    .font(.caption)
                    .lineLimit(3)
            }

            Spacer(minLength: 12)

            BattleStatusCell(
                label: "Stored",
                detail: "raw",
                symbol: "tray.full",
                tint: .orange,
                isStrong: true
            )
            .frame(width: 112)

            BattleStatusCell(
                label: state.label,
                detail: progress.map(progressDetail) ?? "queued",
                symbol: state.symbol,
                tint: state.tint,
                isStrong: state == .fineKeep || state == .fineVerifying
            )
            .frame(width: 132)
        }
        .padding(12)
        .background(Color(nsColor: .textBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .stroke(rowStroke.opacity(state == .fineKeep ? 0.34 : 0.10))
        )
    }

    private var rowStroke: Color {
        switch state {
        case .pending, .embedding:
            .orange
        case .filteredOut, .fineDiscard:
            .gray
        case .coarseOnly, .fineVerifying, .fineKeep:
            state.tint
        }
    }

    private func progressDetail(_ progress: EPICChunkProgress) -> String {
        if let score = progress.score {
            return "\(progress.detail) · \(String(format: "%.3f", score))"
        }
        return progress.detail
    }
}

private struct BattleStatusCell: View {
    let label: String
    let detail: String
    let symbol: String
    let tint: Color
    let isStrong: Bool

    var body: some View {
        VStack(spacing: 5) {
            Image(systemName: symbol)
                .font(.caption.weight(.bold))
                .foregroundStyle(tint)
                .frame(width: 26, height: 26)
                .background(tint.opacity(isStrong ? 0.18 : 0.10))
                .clipShape(Circle())

            Text(label)
                .font(.caption.weight(.bold))
                .foregroundStyle(tint)
                .lineLimit(1)
                .minimumScaleFactor(0.72)

            Text(detail)
                .font(.caption2.monospacedDigit())
                .foregroundStyle(.secondary)
                .lineLimit(1)
                .minimumScaleFactor(0.70)
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 7)
        .frame(maxWidth: .infinity, minHeight: 76)
        .background(tint.opacity(isStrong ? 0.12 : 0.06))
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
    }
}

private struct SelectionPill: View {
    let label: String
    let symbol: String
    let tint: Color

    var body: some View {
        HStack(spacing: 6) {
            Image(systemName: symbol)
            Text(label)
                .lineLimit(1)
        }
        .font(.caption.weight(.semibold))
        .foregroundStyle(tint)
        .padding(.horizontal, 9)
        .padding(.vertical, 5)
        .frame(maxWidth: .infinity)
        .background(tint.opacity(0.11))
        .clipShape(Capsule())
    }
}

private struct ResultMetricTile: View {
    let title: String
    let value: String
    let detail: String
    let tint: Color
    let symbol: String

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Image(systemName: symbol)
                .foregroundStyle(tint)
                .frame(width: 28, height: 28)
                .background(tint.opacity(0.12))
                .clipShape(Circle())
            Text(value)
                .font(.system(size: 24, weight: .bold, design: .rounded))
                .lineLimit(1)
                .minimumScaleFactor(0.72)
            Text(title)
                .font(.caption.weight(.semibold))
            Text(detail)
                .font(.caption2)
                .foregroundStyle(.secondary)
                .lineLimit(1)
        }
        .padding(14)
        .frame(maxWidth: .infinity, minHeight: 130, alignment: .leading)
        .background(Color(nsColor: .textBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
    }
}

private enum ResultChunkOutcome {
    case epicKept
    case fineRejected
    case coarseCandidate
    case coarseFiltered

    init(entries: [EPICMemoryEntry], candidate: CoarseCandidate?, evaluation: FineEvaluation?) {
        if !entries.isEmpty {
            self = .epicKept
        } else if evaluation != nil {
            self = .fineRejected
        } else if candidate != nil {
            self = .coarseCandidate
        } else {
            self = .coarseFiltered
        }
    }

    var label: String {
        switch self {
        case .epicKept: "EPIC kept"
        case .fineRejected: "LLM rejected"
        case .coarseCandidate: "Coarse match"
        case .coarseFiltered: "Below tau"
        }
    }

    var detail: String {
        switch self {
        case .epicKept: "instruction stored"
        case .fineRejected: "not preference-aligned"
        case .coarseCandidate: "awaiting final check"
        case .coarseFiltered: "not indexed by EPIC"
        }
    }

    var symbol: String {
        switch self {
        case .epicKept: "checkmark.seal.fill"
        case .fineRejected: "xmark.seal"
        case .coarseCandidate: "line.3.horizontal.decrease.circle"
        case .coarseFiltered: "minus.circle"
        }
    }

    var tint: Color {
        switch self {
        case .epicKept: .teal
        case .fineRejected: .red
        case .coarseCandidate: .cyan
        case .coarseFiltered: .gray
        }
    }
}

private struct ResultChunkCard: View {
    let chunk: DocumentChunk
    let entries: [EPICMemoryEntry]
    let candidate: CoarseCandidate?
    let evaluation: FineEvaluation?
    let action: () -> Void

    private var outcome: ResultChunkOutcome {
        ResultChunkOutcome(entries: entries, candidate: candidate, evaluation: evaluation)
    }

    var body: some View {
        Button(action: action) {
            VStack(alignment: .leading, spacing: 11) {
                HStack(alignment: .top, spacing: 8) {
                    Text("Chunk \(chunk.index)")
                        .font(.headline.weight(.bold))
                        .lineLimit(1)
                    Spacer()
                    SelectionPill(label: outcome.label, symbol: outcome.symbol, tint: outcome.tint)
                        .frame(width: 118)
                }

                Text(chunk.preview)
                    .font(.caption)
                    .foregroundStyle(.primary)
                    .lineLimit(4)
                    .frame(maxWidth: .infinity, minHeight: 62, alignment: .topLeading)

                HStack(spacing: 8) {
                    ResultCardMetric(label: "Raw", value: chunk.byteCount.memoryString, tint: .orange)
                    ResultCardMetric(label: "EPIC", value: epicMetric, tint: outcome.tint)
                }

                Divider()

                VStack(alignment: .leading, spacing: 4) {
                    Label("Existing RAG keeps the raw chunk", systemImage: "tray.full")
                        .foregroundStyle(.orange)
                    Label(outcome.detail, systemImage: outcome.symbol)
                        .foregroundStyle(outcome.tint)
                    Text(preferencePreview)
                        .foregroundStyle(.secondary)
                        .lineLimit(2)
                }
                .font(.caption2.weight(.semibold))
            }
            .padding(13)
            .frame(maxWidth: .infinity, minHeight: 198, alignment: .topLeading)
            .background(Color(nsColor: .textBackgroundColor))
            .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: 8, style: .continuous)
                    .stroke(outcome.tint.opacity(0.22))
            )
        }
        .buttonStyle(.plain)
    }

    private var epicMetric: String {
        if entries.isEmpty {
            return "0 inst."
        }
        return "\(entries.count) inst."
    }

    private var preferencePreview: String {
        if let preference = entries.first?.preference {
            return preference
        }
        if let match = evaluation?.candidateMatches.first ?? candidate?.matches.first {
            return "\(match.preference) · \(String(format: "%.3f", match.score))"
        }
        return "No relevant preference above threshold."
    }
}

private struct ResultCardMetric: View {
    let label: String
    let value: String
    let tint: Color

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(label)
                .font(.caption2.weight(.semibold))
                .foregroundStyle(.secondary)
            Text(value)
                .font(.caption.monospacedDigit().weight(.bold))
                .foregroundStyle(tint)
                .lineLimit(1)
                .minimumScaleFactor(0.72)
        }
        .padding(.horizontal, 9)
        .padding(.vertical, 7)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(tint.opacity(0.09))
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
    }
}

private struct ResultChunkDetailSheet: View {
    @Environment(\.dismiss) private var dismiss

    let chunk: DocumentChunk
    let entries: [EPICMemoryEntry]
    let candidate: CoarseCandidate?
    let evaluation: FineEvaluation?

    private var outcome: ResultChunkOutcome {
        ResultChunkOutcome(entries: entries, candidate: candidate, evaluation: evaluation)
    }

    private var preferenceMatches: [PreferenceMatch] {
        if let evaluation {
            return evaluation.candidateMatches
        }
        return candidate?.matches ?? []
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack(alignment: .top, spacing: 12) {
                Image(systemName: outcome.symbol)
                    .font(.title2.weight(.bold))
                    .foregroundStyle(outcome.tint)
                    .frame(width: 42, height: 42)
                    .background(outcome.tint.opacity(0.13))
                    .clipShape(Circle())

                VStack(alignment: .leading, spacing: 3) {
                    Text("Chunk \(chunk.index)")
                        .font(.system(size: 24, weight: .bold, design: .rounded))
                    Text("\(chunk.wordCount) words · \(chunk.byteCount.memoryString) raw document")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }

                Spacer()

                SelectionPill(label: outcome.label, symbol: outcome.symbol, tint: outcome.tint)
                    .frame(width: 130)

                Button("Done") {
                    dismiss()
                }
                .keyboardShortcut(.defaultAction)
            }

            HStack(spacing: 10) {
                ResultDecisionTile(title: "Existing RAG", value: "Raw kept", detail: "indiscriminate indexing", symbol: "tray.full", tint: .orange)
                ResultDecisionTile(title: "EPIC", value: outcome.label, detail: outcome.detail, symbol: outcome.symbol, tint: outcome.tint)
                ResultDecisionTile(title: "Instructions", value: "\(entries.count)", detail: "stored for retrieval", symbol: "text.badge.checkmark", tint: .teal)
            }

            HStack(alignment: .top, spacing: 14) {
                ResultDetailSection(title: "Raw Document", symbol: "doc.text", tint: .orange) {
                    ScrollView {
                        Text(chunk.text)
                            .font(.body)
                            .lineSpacing(3)
                            .textSelection(.enabled)
                            .frame(maxWidth: .infinity, alignment: .topLeading)
                    }
                    .frame(minHeight: 390)
                }

                VStack(alignment: .leading, spacing: 14) {
                    ResultDetailSection(title: "Relevant Preference", symbol: "person.text.rectangle", tint: .cyan) {
                        if preferenceMatches.isEmpty {
                            DetailEmptyLine(text: "No preference exceeded the coarse threshold.")
                        } else {
                            VStack(alignment: .leading, spacing: 10) {
                                ForEach(preferenceMatches) { match in
                                    PreferenceDetailLine(match: match)
                                }
                            }
                        }
                    }

                    ResultDetailSection(title: "Instruction", symbol: "text.badge.checkmark", tint: .teal) {
                        if entries.isEmpty {
                            VStack(alignment: .leading, spacing: 7) {
                                DetailEmptyLine(text: "No instruction was stored for this chunk.")
                                if let rejectedReason = evaluation?.rejectedReason, !rejectedReason.isEmpty {
                                    Text(rejectedReason)
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                        .textSelection(.enabled)
                                }
                            }
                        } else {
                            VStack(alignment: .leading, spacing: 12) {
                                ForEach(entries) { entry in
                                    InstructionDetailLine(entry: entry)
                                }
                            }
                        }
                    }
                }
                .frame(width: 360)
            }
        }
        .padding(22)
        .frame(width: 900, height: 680)
        .background(Color(nsColor: .windowBackgroundColor))
    }
}

private struct ResultDecisionTile: View {
    let title: String
    let value: String
    let detail: String
    let symbol: String
    let tint: Color

    var body: some View {
        HStack(spacing: 9) {
            Image(systemName: symbol)
                .foregroundStyle(tint)
                .frame(width: 28, height: 28)
                .background(tint.opacity(0.12))
                .clipShape(Circle())
            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(.caption2.weight(.semibold))
                    .foregroundStyle(.secondary)
                Text(value)
                    .font(.caption.weight(.bold))
                    .lineLimit(1)
                Text(detail)
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
            }
            Spacer(minLength: 0)
        }
        .padding(10)
        .frame(maxWidth: .infinity, minHeight: 68, alignment: .leading)
        .background(Color(nsColor: .textBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
    }
}

private struct ResultDetailSection<Content: View>: View {
    let title: String
    let symbol: String
    let tint: Color
    @ViewBuilder let content: Content

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 7) {
                Image(systemName: symbol)
                    .foregroundStyle(tint)
                Text(title)
                    .font(.headline)
                Spacer()
            }

            content
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .topLeading)
        .background(Color(nsColor: .textBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
    }
}

private struct PreferenceDetailLine: View {
    let match: PreferenceMatch

    var body: some View {
        VStack(alignment: .leading, spacing: 5) {
            HStack(spacing: 7) {
                Image(systemName: match.kind.symbolName)
                    .foregroundStyle(.cyan)
                Text(match.kind.label)
                    .font(.caption.weight(.bold))
                Spacer()
                Text(String(format: "%.3f", match.score))
                    .font(.caption.monospacedDigit().weight(.bold))
                    .foregroundStyle(.cyan)
            }
            Text(match.preference)
                .font(.caption)
                .textSelection(.enabled)
            Text(match.matchedTerms.joined(separator: ", "))
                .font(.caption2)
                .foregroundStyle(.secondary)
        }
        .padding(.bottom, 8)
        .overlay(alignment: .bottom) {
            Divider()
        }
    }
}

private struct InstructionDetailLine: View {
    let entry: EPICMemoryEntry

    var body: some View {
        VStack(alignment: .leading, spacing: 7) {
            HStack(spacing: 7) {
                Image(systemName: entry.kind.symbolName)
                    .foregroundStyle(.teal)
                Text(entry.kind.label)
                    .font(.caption.weight(.bold))
                Spacer()
            }
            Text(entry.preference)
                .font(.caption2.weight(.semibold))
                .foregroundStyle(.secondary)
                .textSelection(.enabled)
            Text(entry.instruction)
                .font(.caption)
                .textSelection(.enabled)
            if !entry.rationale.isEmpty {
                Text(entry.rationale)
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                    .textSelection(.enabled)
            }
        }
        .padding(.bottom, 8)
        .overlay(alignment: .bottom) {
            Divider()
        }
    }
}

private struct DetailEmptyLine: View {
    let text: String

    var body: some View {
        Text(text)
            .font(.caption)
            .foregroundStyle(.secondary)
            .frame(maxWidth: .infinity, alignment: .leading)
    }
}

private struct ResultPanel<Content: View>: View {
    let title: String
    let symbol: String
    let tint: Color
    @ViewBuilder let content: Content

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 8) {
                Image(systemName: symbol)
                    .foregroundStyle(tint)
                Text(title)
                    .font(.headline)
                Spacer()
            }

            content
        }
        .padding(14)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .background(Color(nsColor: .controlBackgroundColor).opacity(0.65))
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
    }
}

private struct CompactChunkLine: View {
    let chunk: DocumentChunk
    let stateLabel: String
    let tint: Color

    var body: some View {
        HStack(spacing: 10) {
            Text("\(chunk.index)")
                .font(.caption.monospacedDigit().weight(.bold))
                .foregroundStyle(.white)
                .frame(width: 24, height: 24)
                .background(tint)
                .clipShape(Circle())
            Text(chunk.preview)
                .font(.caption)
                .lineLimit(2)
            Spacer()
            Text(stateLabel)
                .font(.caption2.weight(.bold))
                .foregroundStyle(tint)
        }
        .padding(10)
        .background(Color(nsColor: .textBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
    }
}

private struct InstructionLine: View {
    let entry: EPICMemoryEntry

    var body: some View {
        VStack(alignment: .leading, spacing: 7) {
            HStack {
                Image(systemName: entry.kind.symbolName)
                    .foregroundStyle(.teal)
                Text("Chunk \(entry.chunk.index)")
                    .font(.caption.weight(.bold))
                Text(entry.kind.label)
                    .font(.caption2.weight(.semibold))
                    .foregroundStyle(.secondary)
                Spacer()
            }

            Text(entry.instruction)
                .font(.caption)
                .lineLimit(3)

            Text(entry.rationale)
                .font(.caption2)
                .foregroundStyle(.secondary)
                .lineLimit(2)
        }
        .padding(10)
        .background(Color(nsColor: .textBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
    }
}

private struct ErrorBanner: View {
    let message: String

    var body: some View {
        HStack(spacing: 10) {
            Image(systemName: "exclamationmark.triangle.fill")
                .foregroundStyle(.orange)
            Text(message)
                .font(.caption)
                .lineLimit(2)
            Spacer()
        }
        .padding(12)
        .background(.orange.opacity(0.11))
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
    }
}

private struct LoadingPanel: View {
    let title: String

    var body: some View {
        VStack(spacing: 12) {
            ProgressView()
            Text(title)
                .font(.headline)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color(nsColor: .controlBackgroundColor).opacity(0.45))
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
    }
}

private struct EmptyState: View {
    let symbol: String
    let title: String
    let detail: String

    var body: some View {
        VStack(spacing: 9) {
            Image(systemName: symbol)
                .font(.largeTitle)
                .foregroundStyle(.secondary)
            Text(title)
                .font(.headline)
            Text(detail)
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .padding(24)
        .background(Color(nsColor: .controlBackgroundColor).opacity(0.45))
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
    }
}

// ── Generation Screen extension ───────────────────────────────────────────
extension ContentView {
    var generationScreen: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack(alignment: .top) {
                ScreenTitle(
                    symbol: "bubble.left.and.bubble.right",
                    title: "Generation",
                    subtitle: "Compare EPIC-RAG vs Plain RAG responses"
                )
                Spacer()
                Button { stage = .retrieval } label: {
                    Label("Retrieval", systemImage: "arrow.left")
                }
                Button {
                    guard !demo.generationQuestion.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return }
                    demo.runGenerate()
                } label: {
                    Label(demo.isGenerating ? "Generating…" : "Generate", systemImage: "sparkles")
                }
                .buttonStyle(.borderedProminent)
                .disabled(demo.isGenerating || demo.generationQuestion.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || !demo.indexReady)

                Button {
                    stage = .evaluation
                    if demo.generationComplete && demo.evaluationResult == nil && !demo.isEvaluating {
                        demo.runEvaluate()
                    }
                } label: {
                    Label("Evaluate", systemImage: "checkmark.seal")
                }
                .disabled(!demo.generationComplete)
            }

            // Corpus banner + load button
            HStack(spacing: 10) {
                Image(systemName: "memorychip")
                    .foregroundStyle(.teal)
                Text("Generating with persona \(demo.persona.personaIndex)'s **EPIC pre-indexed memory** over the full corpus (Wikipedia, Reddit, arXiv, and more).")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
                Spacer()
                if demo.isLoadingPersona {
                    ProgressView().controlSize(.small)
                } else {
                    Button {
                        demo.loadPersonaIndex()
                    } label: {
                        Label(demo.personaLoaded ? "Reload Persona \(demo.persona.personaIndex)" : "Load Corpus Index",
                              systemImage: demo.personaLoaded ? "arrow.clockwise" : "arrow.down.circle")
                            .font(.caption.weight(.semibold))
                    }
                    .buttonStyle(.bordered)
                    .tint(.teal)
                }
            }
            .padding(.horizontal, 14)
            .padding(.vertical, 10)
            .background(Color.teal.opacity(0.07))
            .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))

            // Curated, pre-vetted questions — instant, no LLM calls
            GuideBanner(text: "Click a pre-vetted question for an instant result, or type your own and click \"Generate\" for a live run.")

            if demo.isLoadingCuratedQuestions {
                HStack(spacing: 8) {
                    ProgressView().controlSize(.small)
                    Text("Loading curated questions…").font(.caption).foregroundStyle(.secondary)
                }
            } else if !demo.curatedQuestions.isEmpty {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 10) {
                        ForEach(demo.curatedQuestions) { qa in
                            CuratedQuestionChip(
                                qa: qa,
                                isSelected: demo.selectedCuratedQA?.id == qa.id
                            ) {
                                demo.selectCuratedQA(qa)
                            }
                        }
                    }
                    .padding(.vertical, 2)
                }
            } else if let err = demo.curatedQuestionsError {
                Text("Curated questions unavailable: \(err)")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }

            // Question input (live generation)
            HStack(spacing: 10) {
                TextField("...or type your own question", text: $demo.generationQuestion)
                    .textFieldStyle(.roundedBorder)
                    .font(.title3)
                    .onSubmit { demo.runGenerate() }

                if !demo.indexReady {
                    Label("Load a persona or run EPIC indexing first", systemImage: "exclamationmark.triangle")
                        .font(.caption)
                        .foregroundStyle(.orange)
                }
            }

            if let err = demo.generationError {
                ErrorBanner(message: err)
            }

            // Side-by-side responses
            if demo.isGenerating || !demo.epicResponseText.isEmpty || !demo.ragResponseText.isEmpty {
                HStack(alignment: .top, spacing: 12) {
                    GenerationPanel(
                        title: "EPIC-RAG",
                        subtitle: "\(demo.epicRetrievedDocs.count) pref-aligned docs",
                        color: .teal,
                        symbol: "bolt.horizontal.circle.fill",
                        responseText: demo.epicResponseText,
                        isLoading: demo.isGenerating && demo.epicResponseText.isEmpty,
                        docs: demo.epicRetrievedDocs,
                        isEPIC: true,
                        retrLatencyMs: demo.epicRetrLatencyMs,
                        indexBytes: demo.epicIndexBytes,
                        entryCount: demo.epicEntryCount
                    )
                    GenerationPanel(
                        title: "Plain RAG",
                        subtitle: "\(demo.ragRetrievedDocs.count) raw chunks",
                        color: .orange,
                        symbol: "tray.full",
                        responseText: demo.ragResponseText,
                        isLoading: demo.isGenerating && demo.ragResponseText.isEmpty,
                        docs: demo.ragRetrievedDocs,
                        isEPIC: false,
                        retrLatencyMs: demo.ragRetrLatencyMs,
                        indexBytes: demo.ragIndexBytes,
                        entryCount: demo.ragChunkCount
                    )
                }
            } else if demo.indexReady {
                EmptyState(
                    symbol: "bubble.left.and.bubble.right",
                    title: "Ask a question",
                    detail: "Type a question above and press Generate to compare EPIC-RAG vs Plain RAG."
                )
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                VStack(spacing: 16) {
                    // Quick load from pre-indexed corpus
                    VStack(spacing: 10) {
                        Label("Load Pre-indexed Memory", systemImage: "memorychip")
                            .font(.headline)
                        Text("Instantly load persona \(demo.persona.personaIndex)'s EPIC index built from the full corpus.")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                            .multilineTextAlignment(.center)
                        if demo.isLoadingPersona {
                            ProgressView("Loading persona \(demo.persona.personaIndex)…")
                                .controlSize(.small)
                        } else {
                            Button {
                                demo.loadPersonaIndex()
                            } label: {
                                Label("Load Persona \(demo.persona.personaIndex)", systemImage: "arrow.down.circle.fill")
                            }
                            .buttonStyle(.borderedProminent)
                            .tint(.teal)
                        }
                        if let err = demo.personaLoadError {
                            Text(err)
                                .font(.caption)
                                .foregroundStyle(.red)
                                .multilineTextAlignment(.center)
                        }
                    }
                    .padding(20)
                    .background(Color.teal.opacity(0.07))
                    .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))

                    Text("— or —")
                        .font(.caption)
                        .foregroundStyle(.secondary)

                    EmptyState(
                        symbol: "bolt.fill",
                        title: "Run live EPIC indexing",
                        detail: "Go back to the Indexing tab to run EPIC on a Wikipedia article."
                    )
                }
                .frame(maxWidth: 420)
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
        }
        .padding(26)
    }

    var evaluationScreen: some View {
        VStack(alignment: .leading, spacing: 18) {
            HStack(alignment: .top) {
                ScreenTitle(
                    symbol: "checkmark.seal",
                    title: "Evaluation",
                    subtitle: "Preference following: 4-metric analysis"
                )
                Spacer()
                Button { stage = .generation } label: {
                    Label("Generation", systemImage: "arrow.left")
                }
                Button {
                    if demo.generationComplete && !demo.isEvaluating {
                        demo.runEvaluate()
                    }
                } label: {
                    Label(demo.isEvaluating ? "Evaluating…" : "Re-Evaluate", systemImage: "arrow.clockwise")
                }
                .disabled(!demo.generationComplete || demo.isEvaluating)
            }

            if let err = demo.evaluationError {
                ErrorBanner(message: err)
            }

            if demo.isEvaluating {
                LoadingPanel(title: "Running 4-metric evaluation with \(demo.runtimeFootprint?.llm ?? "LLM")…")
            } else if let result = demo.evaluationResult {
                VStack(alignment: .leading, spacing: 16) {
                    // Preference used
                    if !demo.topPreference.isEmpty {
                        HStack(alignment: .top, spacing: 12) {
                            Image(systemName: "person.crop.circle.badge.checkmark")
                                .foregroundStyle(.teal)
                                .frame(width: 28, height: 28)
                                .background(.teal.opacity(0.12))
                                .clipShape(Circle())
                            VStack(alignment: .leading, spacing: 3) {
                                Text("Evaluated Preference")
                                    .font(.caption.weight(.semibold))
                                    .foregroundStyle(.secondary)
                                Text(demo.topPreference)
                                    .font(.body)
                            }
                        }
                        .padding(14)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(Color(nsColor: .textBackgroundColor))
                        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
                    }

                    HStack(alignment: .top, spacing: 12) {
                        EvaluationSidePanel(
                            title: "EPIC-RAG",
                            color: .teal,
                            symbol: "bolt.horizontal.circle.fill",
                            result: result.epic,
                            response: demo.epicResponseText
                        )
                        EvaluationSidePanel(
                            title: "Plain RAG",
                            color: .orange,
                            symbol: "tray.full",
                            result: result.rag,
                            response: demo.ragResponseText
                        )
                    }
                }
            } else if !demo.generationComplete {
                EmptyState(
                    symbol: "bubble.left.and.bubble.right",
                    title: "Generate responses first",
                    detail: "Go back to Generation and run a question before evaluating."
                )
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                EmptyState(
                    symbol: "checkmark.seal",
                    title: "Ready to evaluate",
                    detail: "Press Evaluate to run the 4-metric preference following analysis."
                )
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
        }
        .padding(26)
        .onAppear {
            if demo.generationComplete && demo.evaluationResult == nil && !demo.isEvaluating {
                demo.runEvaluate()
            }
        }
    }
}

// ── Generation Panel ──────────────────────────────────────────────────────

// ── Curated question chip ────────────────────────────────────────────────

private struct CuratedQuestionChip: View {
    let qa: CuratedQA
    let isSelected: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            VStack(alignment: .leading, spacing: 6) {
                HStack(spacing: 6) {
                    if qa.isStrongContrast {
                        Label("EPIC wins", systemImage: "star.fill")
                            .font(.caption2.weight(.bold))
                            .foregroundStyle(.white)
                            .padding(.horizontal, 7)
                            .padding(.vertical, 2)
                            .background(Color.green)
                            .clipShape(Capsule())
                    }
                    Spacer()
                }
                Text(qa.question)
                    .font(.callout.weight(.semibold))
                    .foregroundStyle(.primary)
                    .lineLimit(3)
                    .multilineTextAlignment(.leading)
            }
            .padding(12)
            .frame(width: 220, alignment: .topLeading)
            .background(isSelected ? Color.teal.opacity(0.18) : Color.teal.opacity(0.08))
            .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: 10, style: .continuous)
                    .stroke(Color.teal.opacity(isSelected ? 0.7 : 0.2), lineWidth: isSelected ? 2 : 1)
            )
        }
        .buttonStyle(.plain)
    }
}

private struct GenerationPanel: View {
    let title: String
    let subtitle: String
    let color: Color
    let symbol: String
    let responseText: String
    let isLoading: Bool
    let docs: [RetrievedDoc]
    let isEPIC: Bool
    var retrLatencyMs: Double? = nil
    var indexBytes: Int? = nil
    var entryCount: Int? = nil

    @State private var showDocs = false

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Header
            HStack(spacing: 10) {
                Image(systemName: symbol)
                    .font(.headline.weight(.semibold))
                    .foregroundStyle(color)
                    .frame(width: 34, height: 34)
                    .background(color.opacity(0.12))
                    .clipShape(Circle())
                VStack(alignment: .leading, spacing: 2) {
                    Text(title)
                        .font(.headline.weight(.bold))
                    Text(subtitle)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                Spacer()
                if !docs.isEmpty {
                    Button {
                        withAnimation { showDocs.toggle() }
                    } label: {
                        Label(showDocs ? "Hide docs" : "Show docs", systemImage: showDocs ? "chevron.up" : "chevron.down")
                            .font(.caption)
                    }
                    .buttonStyle(.borderless)
                }
            }

            // Retrieval stat badges
            if retrLatencyMs != nil || indexBytes != nil {
                HStack(spacing: 8) {
                    if let ms = retrLatencyMs {
                        StatBadge(symbol: "clock", label: String(format: "Retrieval %.0f ms", ms), color: color)
                    }
                    if let bytes = indexBytes {
                        let mb = Double(bytes) / 1_048_576.0
                        StatBadge(symbol: "memorychip", label: String(format: "Index %.1f MB", mb), color: color)
                    }
                    if let count = entryCount {
                        StatBadge(symbol: "list.bullet", label: "\(count) entries", color: color)
                    }
                }
            }

            // Retrieved docs (collapsible)
            if showDocs && !docs.isEmpty {
                VStack(alignment: .leading, spacing: 6) {
                    ForEach(docs.prefix(5)) { doc in
                        RetrievedDocRow(doc: doc, isEPIC: isEPIC, color: color)
                    }
                }
                .padding(10)
                .background(color.opacity(0.05))
                .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
            }

            // Response text
            if isLoading {
                HStack(spacing: 10) {
                    ProgressView().controlSize(.small)
                    Text("Generating…")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                .padding(.vertical, 8)
            } else if responseText.isEmpty {
                Text("Waiting…")
                    .font(.body)
                    .foregroundStyle(.secondary)
                    .padding(.vertical, 8)
            } else {
                ScrollView {
                    Text(responseText)
                        .font(.body)
                        .lineSpacing(4)
                        .textSelection(.enabled)
                        .frame(maxWidth: .infinity, alignment: .topLeading)
                }
                .frame(maxHeight: .infinity)
            }
        }
        .padding(14)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .background(Color(nsColor: .textBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .stroke(color.opacity(0.22))
        )
    }
}

struct StatBadge: View {
    let symbol: String
    let label: String
    let color: Color

    var body: some View {
        HStack(spacing: 4) {
            Image(systemName: symbol)
                .font(.caption2.weight(.semibold))
            Text(label)
                .font(.caption2.weight(.semibold))
        }
        .foregroundStyle(color)
        .padding(.horizontal, 8)
        .padding(.vertical, 4)
        .background(color.opacity(0.10))
        .clipShape(Capsule())
    }
}

// ── Mode select card ─────────────────────────────────────────────────────

private struct ModeCard: View {
    let symbol: String
    let title: String
    let detail: String
    let color: Color
    let action: () -> Void

    @State private var isHovering = false

    var body: some View {
        Button(action: action) {
            VStack(alignment: .leading, spacing: 18) {
                Image(systemName: symbol)
                    .font(.system(size: 40, weight: .semibold))
                    .foregroundStyle(color)
                    .frame(width: 72, height: 72)
                    .background(color.opacity(0.12))
                    .clipShape(Circle())
                Text(title)
                    .font(.system(size: 30, weight: .bold, design: .rounded))
                Text(detail)
                    .font(.title3)
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
                Spacer(minLength: 0)
                Label("Start", systemImage: "arrow.right.circle.fill")
                    .font(.title2.weight(.semibold))
                    .foregroundStyle(color)
            }
            .padding(28)
            .frame(maxWidth: .infinity, minHeight: 320, alignment: .topLeading)
            .background(Color(nsColor: .controlBackgroundColor))
            .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: 16, style: .continuous)
                    .stroke(color.opacity(isHovering ? 0.6 : 0.22), lineWidth: isHovering ? 2 : 1)
            )
            .scaleEffect(isHovering ? 1.015 : 1.0)
        }
        .buttonStyle(.plain)
        .onHover { isHovering = $0 }
        .animation(.easeOut(duration: 0.15), value: isHovering)
    }
}

// ── Memory comparison card (Retrieval screen) ──────────────────────────────

// ── Side-by-side memory comparison with reduction factor ───────────────────

private struct MemoryReductionComparison: View {
    let epicEntryCount: Int
    let epicBytes: Int
    let ragChunkCount: Int
    let ragBytes: Int

    private var epicMb: Double { Double(epicBytes) / 1_048_576 }
    private var ragMb: Double { Double(ragBytes) / 1_048_576 }
    private var reductionFactor: Double { epicMb > 0 ? ragMb / epicMb : 0 }

    var body: some View {
        VStack(spacing: 10) {
            HStack(alignment: .top, spacing: 16) {
                MemoryComparisonCard(
                    title: "EPIC Memory",
                    color: .teal,
                    symbol: "bolt.horizontal.circle.fill",
                    entryLabel: "instructions",
                    entryCount: epicEntryCount,
                    bytes: epicBytes
                )
                MemoryComparisonCard(
                    title: "Plain RAG Memory",
                    color: .orange,
                    symbol: "tray.full",
                    entryLabel: "raw chunks",
                    entryCount: ragChunkCount,
                    bytes: ragBytes
                )
            }

            if reductionFactor > 1 {
                HStack(spacing: 6) {
                    Image(systemName: "arrow.down.right.circle.fill")
                        .foregroundStyle(.green)
                    Text(String(format: "EPIC stores %.1f× less than Plain RAG", reductionFactor))
                        .font(.subheadline.weight(.bold))
                        .foregroundStyle(.green)
                }
                .padding(.horizontal, 14)
                .padding(.vertical, 8)
                .background(Color.green.opacity(0.10))
                .clipShape(Capsule())
            }
        }
    }
}

private struct MemoryComparisonCard: View {
    let title: String
    let color: Color
    let symbol: String
    let entryLabel: String
    let entryCount: Int
    let bytes: Int

    private var mb: Double { Double(bytes) / 1_048_576 }

    var body: some View {
        HStack(spacing: 14) {
            Image(systemName: symbol)
                .font(.title2.weight(.semibold))
                .foregroundStyle(color)
                .frame(width: 44, height: 44)
                .background(color.opacity(0.12))
                .clipShape(Circle())
            VStack(alignment: .leading, spacing: 3) {
                Text(title)
                    .font(.subheadline.weight(.bold))
                Text("\(entryCount.formatted()) \(entryLabel)")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            Spacer()
            Text(String(format: "%.1f MB", mb))
                .font(.title3.weight(.bold).monospacedDigit())
                .foregroundStyle(color)
        }
        .padding(16)
        .frame(maxWidth: .infinity)
        .background(color.opacity(0.06))
        .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 12, style: .continuous)
                .stroke(color.opacity(0.2))
        )
    }
}

// ── Animated retrieval step tracker ─────────────────────────────────────

// ── Latency breakdown: shared embedding step + per-system search ───────────

private struct LatencyBreakdownBar: View {
    let embedMs: Double
    let steerMs: Double          // EPIC-only: fold top-1 preference into the query vector
    let matchedPreference: String?
    let epicSearchMs: Double
    let ragSearchMs: Double

    private var epicTotal: Double { embedMs + steerMs + epicSearchMs }
    private var ragTotal: Double { embedMs + ragSearchMs }
    private var maxTotal: Double { max(epicTotal, ragTotal, 0.001) }

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Latency Breakdown")
                .font(.subheadline.weight(.bold))

            epicRow
            ragRow

            HStack(spacing: 14) {
                legendDot(color: .gray, label: "Query embedding (Contriever, shared)")
                legendDot(color: .purple.opacity(0.55), label: "EPIC query steering (fold top-1 preference)")
                legendDot(color: .teal.opacity(0.55), label: "EPIC instruction search")
                legendDot(color: .orange.opacity(0.55), label: "RAG chunk search")
            }
            .font(.caption2)
            .foregroundStyle(.secondary)
        }
        .padding(16)
        .background(Color(nsColor: .controlBackgroundColor).opacity(0.6))
        .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
    }

    private var epicRow: some View {
        VStack(alignment: .leading, spacing: 3) {
            HStack(spacing: 10) {
                Text("EPIC-RAG")
                    .font(.caption.weight(.bold))
                    .foregroundStyle(.teal)
                    .frame(width: 76, alignment: .leading)

                GeometryReader { geo in
                    HStack(spacing: 1) {
                        Rectangle().fill(Color.gray.opacity(0.5))
                            .frame(width: geo.size.width * (embedMs / maxTotal))
                        Rectangle().fill(Color.purple.opacity(0.55))
                            .frame(width: geo.size.width * (steerMs / maxTotal))
                        Rectangle().fill(Color.teal.opacity(0.55))
                            .frame(width: geo.size.width * (epicSearchMs / maxTotal))
                        Spacer(minLength: 0)
                    }
                    .clipShape(RoundedRectangle(cornerRadius: 4, style: .continuous))
                }
                .frame(height: 16)

                Text(String(format: "%.1f ms", epicTotal))
                    .font(.caption.monospacedDigit().weight(.semibold))
                    .frame(width: 60, alignment: .trailing)
            }
            VStack(alignment: .leading, spacing: 1) {
                Text(String(format: "↳ query steering: %.1f ms · instruction search: %.1f ms", steerMs, epicSearchMs))
                    .font(.caption2.weight(.semibold))
                    .foregroundStyle(.teal)
                if let pref = matchedPreference {
                    Text("↳ steered toward: \"\(pref)\"")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                }
            }
            .padding(.leading, 86)
        }
    }

    private var ragRow: some View {
        HStack(spacing: 10) {
            Text("Plain RAG")
                .font(.caption.weight(.bold))
                .foregroundStyle(.orange)
                .frame(width: 76, alignment: .leading)

            GeometryReader { geo in
                HStack(spacing: 1) {
                    Rectangle().fill(Color.gray.opacity(0.5))
                        .frame(width: geo.size.width * (embedMs / maxTotal))
                    Rectangle().fill(Color.orange.opacity(0.55))
                        .frame(width: geo.size.width * (ragSearchMs / maxTotal))
                    Spacer(minLength: 0)
                }
                .clipShape(RoundedRectangle(cornerRadius: 4, style: .continuous))
            }
            .frame(height: 16)

            Text(String(format: "%.1f ms", ragTotal))
                .font(.caption.monospacedDigit().weight(.semibold))
                .frame(width: 60, alignment: .trailing)
        }
    }

    private func legendDot(color: Color, label: String) -> some View {
        HStack(spacing: 4) {
            Circle().fill(color).frame(width: 8, height: 8)
            Text(label)
        }
    }
}

private struct RetrievalStepTracker: View {
    let currentStep: EPICDemoViewModel.RetrievalStep

    private let steps: [EPICDemoViewModel.RetrievalStep] = [.embedding, .searching, .done]

    var body: some View {
        HStack(spacing: 0) {
            ForEach(Array(steps.enumerated()), id: \.element) { index, step in
                let reached = currentStep.rawValue >= step.rawValue
                HStack(spacing: 8) {
                    ZStack {
                        Circle()
                            .fill(reached ? Color.teal : Color.gray.opacity(0.25))
                            .frame(width: 22, height: 22)
                        if step == currentStep && step != .done {
                            ProgressView()
                                .controlSize(.mini)
                                .tint(.white)
                        } else if reached {
                            Image(systemName: "checkmark")
                                .font(.caption2.weight(.bold))
                                .foregroundStyle(.white)
                        }
                    }
                    Text(step.label)
                        .font(.caption.weight(reached ? .semibold : .regular))
                        .foregroundStyle(reached ? .primary : .secondary)
                }
                if index < steps.count - 1 {
                    Rectangle()
                        .fill(reached ? Color.teal.opacity(0.4) : Color.gray.opacity(0.15))
                        .frame(height: 2)
                        .frame(maxWidth: 40)
                }
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
        .background(Color(nsColor: .controlBackgroundColor).opacity(0.6))
        .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
    }
}

// ── Retrieval result panel (doc list + latency, no generation) ─────────────

private struct RetrievalResultPanel: View {
    let title: String
    let color: Color
    let symbol: String
    let latencyMs: Double
    let docs: [RetrievedDoc]
    let isEPIC: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 10) {
                Image(systemName: symbol)
                    .font(.headline.weight(.semibold))
                    .foregroundStyle(color)
                    .frame(width: 32, height: 32)
                    .background(color.opacity(0.12))
                    .clipShape(Circle())
                Text(title)
                    .font(.headline.weight(.bold))
                Spacer()
                StatBadge(symbol: "clock", label: String(format: "%.0f ms", latencyMs), color: color)
            }

            if docs.isEmpty {
                Text("No matches above threshold.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .padding(.vertical, 8)
            } else {
                ScrollView {
                    VStack(alignment: .leading, spacing: 8) {
                        ForEach(Array(docs.prefix(5).enumerated()), id: \.element.id) { index, doc in
                            VStack(alignment: .leading, spacing: 4) {
                                HStack(spacing: 6) {
                                    Text("#\(index + 1)")
                                        .font(.caption2.weight(.bold))
                                        .foregroundStyle(color)
                                    Text(doc.articleTitle)
                                        .font(.caption.weight(.semibold))
                                        .lineLimit(1)
                                    Spacer()
                                    Text(String(format: "score %.2f", doc.score))
                                        .font(.caption2.monospacedDigit())
                                        .foregroundStyle(.secondary)
                                }
                                if isEPIC, let instruction = doc.instruction {
                                    Text(instruction)
                                        .font(.caption2.weight(.medium))
                                        .foregroundStyle(.teal)
                                        .lineLimit(3)
                                }
                                Text(doc.chunkText)
                                    .font(.caption2)
                                    .foregroundStyle(.secondary)
                                    .fixedSize(horizontal: false, vertical: true)
                            }
                            .padding(10)
                            .background(color.opacity(0.05))
                            .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
                        }
                    }
                }
            }
        }
        .padding(14)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .background(Color(nsColor: .textBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .stroke(color.opacity(0.22))
        )
    }
}

private struct RetrievedDocRow: View {
    let doc: RetrievedDoc
    let isEPIC: Bool
    let color: Color

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(doc.articleTitle.isEmpty ? "Document" : doc.articleTitle)
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(.secondary)
                Spacer()
                Text(String(format: "%.3f", doc.score))
                    .font(.caption2.monospacedDigit())
                    .foregroundStyle(color)
            }
            if isEPIC, let instruction = doc.instruction, !instruction.isEmpty {
                Text("Guidance: \(instruction)")
                    .font(.caption2)
                    .foregroundStyle(color.opacity(0.85))
                    .lineLimit(2)
            }
            Text(doc.chunkText.prefix(160) + (doc.chunkText.count > 160 ? "…" : ""))
                .font(.caption2)
                .foregroundStyle(.secondary)
                .lineLimit(3)
        }
        .padding(8)
        .background(Color(nsColor: .controlBackgroundColor).opacity(0.5))
        .clipShape(RoundedRectangle(cornerRadius: 6, style: .continuous))
    }
}

// ── Evaluation Panel ──────────────────────────────────────────────────────

private struct EvaluationSidePanel: View {
    let title: String
    let color: Color
    let symbol: String
    let result: MetricResult
    let response: String

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(spacing: 10) {
                Image(systemName: symbol)
                    .font(.headline.weight(.semibold))
                    .foregroundStyle(color)
                    .frame(width: 34, height: 34)
                    .background(color.opacity(0.12))
                    .clipShape(Circle())
                Text(title)
                    .font(.headline.weight(.bold))
                Spacer()
                PrefFollowingBadge(passing: result.preferenceFollowing)
            }

            // 4 metrics grid
            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 10) {
                EvalMetricBadge(
                    title: "Acknowledges",
                    passing: result.acknow,
                    passSymbol: "checkmark.circle.fill",
                    failSymbol: "minus.circle",
                    passLabel: "Acknowledged",
                    failLabel: "Not acknowledged"
                )
                EvalMetricBadge(
                    title: "No Violation",
                    passing: !result.violate,
                    passSymbol: "checkmark.circle.fill",
                    failSymbol: "xmark.circle.fill",
                    passLabel: "No violation",
                    failLabel: "Violated preference"
                )
                EvalMetricBadge(
                    title: "No Hallucination",
                    passing: !result.hallucinate,
                    passSymbol: "checkmark.circle.fill",
                    failSymbol: "xmark.circle.fill",
                    passLabel: "Accurate recall",
                    failLabel: "Hallucinated pref."
                )
                EvalMetricBadge(
                    title: "Helpful",
                    passing: result.helpful,
                    passSymbol: "checkmark.circle.fill",
                    failSymbol: "xmark.circle.fill",
                    passLabel: "Helpful",
                    failLabel: "Not helpful"
                )
            }

            // Response preview
            VStack(alignment: .leading, spacing: 6) {
                Text("Response")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(.secondary)
                ScrollView {
                    Text(response)
                        .font(.caption)
                        .lineSpacing(3)
                        .textSelection(.enabled)
                        .frame(maxWidth: .infinity, alignment: .topLeading)
                }
                .frame(maxHeight: 220)
            }
            .padding(10)
            .background(Color(nsColor: .controlBackgroundColor).opacity(0.5))
            .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .topLeading)
        .background(Color(nsColor: .textBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .stroke(color.opacity(0.22))
        )
    }
}

private struct PrefFollowingBadge: View {
    let passing: Bool

    var body: some View {
        HStack(spacing: 5) {
            Image(systemName: passing ? "checkmark.seal.fill" : "xmark.seal.fill")
                .font(.caption.weight(.bold))
            Text(passing ? "Preference Following" : "Not Following")
                .font(.caption.weight(.bold))
        }
        .foregroundStyle(passing ? .green : .red)
        .padding(.horizontal, 10)
        .padding(.vertical, 6)
        .background((passing ? Color.green : Color.red).opacity(0.12))
        .clipShape(Capsule())
    }
}

private struct EvalMetricBadge: View {
    let title: String
    let passing: Bool
    let passSymbol: String
    let failSymbol: String
    let passLabel: String
    let failLabel: String

    var tint: Color { passing ? .teal : .red }

    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: passing ? passSymbol : failSymbol)
                .font(.headline.weight(.bold))
                .foregroundStyle(tint)
                .frame(width: 30, height: 30)
                .background(tint.opacity(0.12))
                .clipShape(Circle())
            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(.caption2.weight(.semibold))
                    .foregroundStyle(.secondary)
                Text(passing ? passLabel : failLabel)
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(tint)
                    .lineLimit(1)
                    .minimumScaleFactor(0.75)
            }
            Spacer(minLength: 0)
        }
        .padding(10)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(tint.opacity(0.07))
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .stroke(tint.opacity(0.18))
        )
    }
}
