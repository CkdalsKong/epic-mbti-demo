import Foundation

enum TextChunker {
    static func chunk(article: WikiArticle, targetWords: Int = 100) -> [DocumentChunk] {
        let sentences = sentenceSegments(from: article.extract)

        var chunks: [DocumentChunk] = []
        var buffer: [String] = []
        var wordCount = 0

        for sentence in sentences {
            let sentenceWordCount = TextTools.tokensIncludingShortWords(sentence).count
            guard sentenceWordCount > 0 else { continue }

            if sentenceWordCount >= targetWords {
                appendChunk(from: &buffer, wordCount: &wordCount, article: article, chunks: &chunks)
                chunks.append(DocumentChunk(articleTitle: article.title, index: chunks.count + 1, text: sentence.collapsedWhitespace))
                continue
            }

            if wordCount + sentenceWordCount > targetWords {
                appendChunk(from: &buffer, wordCount: &wordCount, article: article, chunks: &chunks)
            }

            buffer.append(sentence)
            wordCount += sentenceWordCount
        }

        appendChunk(from: &buffer, wordCount: &wordCount, article: article, chunks: &chunks)

        if chunks.isEmpty, !article.extract.isEmpty {
            chunks.append(DocumentChunk(articleTitle: article.title, index: 1, text: article.extract.prefixText(900)))
        }

        return chunks
    }

    private static func sentenceSegments(from text: String) -> [String] {
        var sentences: [String] = []
        text.enumerateSubstrings(in: text.startIndex..<text.endIndex, options: [.bySentences, .localized]) { substring, _, _, _ in
            guard let substring else { return }
            let sentence = substring.collapsedWhitespace
            if !sentence.isEmpty {
                sentences.append(sentence)
            }
        }

        if sentences.isEmpty {
            let fallback = text.collapsedWhitespace
            return fallback.isEmpty ? [] : [fallback]
        }
        return sentences
    }

    private static func appendChunk(
        from buffer: inout [String],
        wordCount: inout Int,
        article: WikiArticle,
        chunks: inout [DocumentChunk]
    ) {
        guard !buffer.isEmpty else { return }
        let chunkText = buffer.joined(separator: " ").collapsedWhitespace
        chunks.append(DocumentChunk(articleTitle: article.title, index: chunks.count + 1, text: chunkText))
        buffer = []
        wordCount = 0
    }
}

struct EPICIndexer {
    let threshold: Double

    func existingRAGMemory(from chunks: [DocumentChunk]) -> [ExistingMemoryEntry] {
        chunks.map(ExistingMemoryEntry.init(chunk:))
    }

    func coarseFilter(chunks: [DocumentChunk], persona: PersonaPreset) -> [CoarseCandidate] {
        let signals = PreferenceAnalyzer.signals(for: persona)
        return chunks.compactMap { chunk in
            let normalizedText = TextTools.normalized(chunk.text)
            let tokenSet = Set(TextTools.tokensIncludingShortWords(chunk.text))
            let matches = signals.compactMap { signal -> PreferenceMatch? in
                let termHits = signal.terms.filter { TextTools.contains(term: $0, in: normalizedText, tokenSet: tokenSet) }
                let strongHits = signal.strongTerms.filter { TextTools.contains(term: $0, in: normalizedText, tokenSet: tokenSet) }
                let uniqueHits = Array(Set(termHits + strongHits)).sorted()
                guard !uniqueHits.isEmpty else { return nil }

                let score = min(1.0, Double(termHits.count) * 0.075 + Double(strongHits.count) * 0.18)
                guard score >= threshold else { return nil }

                return PreferenceMatch(
                    preferenceIndex: signal.index,
                    preference: signal.preference,
                    kind: signal.kind,
                    score: score,
                    matchedTerms: Array(uniqueHits.prefix(8))
                )
            }
            .sorted { $0.score > $1.score }

            guard !matches.isEmpty else { return nil }
            return CoarseCandidate(chunk: chunk, matches: Array(matches.prefix(3)))
        }
    }

    func fineVerify(candidates: [CoarseCandidate], persona: PersonaPreset) -> [FineEvaluation] {
        let signals = PreferenceAnalyzer.signals(for: persona)
        let signalByIndex = Dictionary(uniqueKeysWithValues: signals.map { ($0.index, $0) })

        return candidates.map { candidate in
            var entries: [EPICMemoryEntry] = []
            var rejectionNotes: [String] = []

            for match in candidate.matches {
                guard let signal = signalByIndex[match.preferenceIndex] else { continue }
                let strongHits = match.matchedTerms.filter { signal.strongTerms.contains($0) }
                let hasConcreteSignal = !strongHits.isEmpty || match.matchedTerms.count >= signal.minimumEvidenceTerms

                if hasConcreteSignal {
                    let instruction = InstructionGenerator.instruction(for: signal, chunk: candidate.chunk, matchedTerms: match.matchedTerms)
                    let rationale = "Kept because the chunk contains \(match.matchedTerms.prefix(4).joined(separator: ", ")) and maps to preference \(match.preferenceIndex + 1)."
                    entries.append(
                        EPICMemoryEntry(
                            chunk: candidate.chunk,
                            preferenceIndex: match.preferenceIndex,
                            preference: match.preference,
                            kind: match.kind,
                            instruction: instruction,
                            rationale: rationale,
                            matchedTerms: match.matchedTerms
                        )
                    )
                } else {
                    rejectionNotes.append("Preference \(match.preferenceIndex + 1) only had weak lexical overlap: \(match.matchedTerms.joined(separator: ", ")).")
                }
            }

            return FineEvaluation(
                chunk: candidate.chunk,
                candidateMatches: candidate.matches,
                keptEntries: entries,
                rejectedReason: entries.isEmpty ? (rejectionNotes.first ?? "Fine verification found no concrete preference alignment.") : nil
            )
        }
    }
}

private struct PreferenceSignal {
    let index: Int
    let preference: String
    let kind: PreferenceKind
    let terms: [String]
    let strongTerms: [String]
    let minimumEvidenceTerms: Int
}

private enum PreferenceAnalyzer {
    static func signals(for persona: PersonaPreset) -> [PreferenceSignal] {
        persona.preferenceBlocks.enumerated().map { index, block in
            let kind = kind(for: block.preference)
            let expanded = expandedTerms(for: kind)
            let baseTerms = Set(TextTools.tokens(block.preference))
            let allTerms = Array(baseTerms.union(expanded.terms)).sorted()
            let strongTerms = Array(expanded.strongTerms).sorted()
            return PreferenceSignal(
                index: index,
                preference: block.preference,
                kind: kind,
                terms: allTerms,
                strongTerms: strongTerms.isEmpty ? allTerms : strongTerms,
                minimumEvidenceTerms: expanded.minimumEvidenceTerms
            )
        }
    }

    private static func kind(for preference: String) -> PreferenceKind {
        let normalized = TextTools.normalized(preference)
        if normalized.contains("electric vehicles") { return .electricVehicles }
        if normalized.contains("pickup trucks") { return .pickupTrucks }
        if normalized.contains("european car brands") { return .europeanCars }
        if normalized.contains("backtracking") { return .repetitiveGames }
        if normalized.contains("raw vegan") { return .rawVegan }
        if normalized.contains("gimmicky dining") || normalized.contains("quality food") { return .restaurantQuality }
        if normalized.contains("spicy food") { return .spicyFood }
        if normalized.contains("strict vegan") || normalized.contains("animal derived") { return .vegan }
        if normalized.contains("shelters") || normalized.contains("breeders") { return .shelterPets }
        if normalized.contains("scratchy") || normalized.contains("wool") { return .textureSensitive }
        return .generic
    }

    private static func expandedTerms(for kind: PreferenceKind) -> (terms: Set<String>, strongTerms: Set<String>, minimumEvidenceTerms: Int) {
        switch kind {
        case .electricVehicles:
            return (
                [
                    "automobile", "battery", "battery electric", "bev", "car", "cars", "charging",
                    "diesel", "electric", "electric car", "electric vehicle", "ev", "fuel",
                    "gas", "gas powered", "gasoline", "hybrid", "internal combustion",
                    "plug in", "range", "vehicle", "vehicles"
                ],
                ["battery electric", "charging", "electric", "electric vehicle", "ev", "gasoline", "internal combustion"],
                2
            )
        case .pickupTrucks:
            return (
                [
                    "bed", "body on frame", "cargo bed", "chevrolet silverado", "f series",
                    "ford f", "full size", "off road", "pickup", "pickup truck", "ram",
                    "silverado", "tow", "towing", "truck", "trucks"
                ],
                ["cargo bed", "pickup", "pickup truck", "tow", "towing", "truck"],
                1
            )
        case .europeanCars:
            return (
                [
                    "alfa romeo", "audi", "bmw", "citroen", "europe", "european",
                    "fiat", "french", "german", "italian", "mercedes", "peugeot",
                    "porsche", "renault", "volkswagen", "volvo"
                ],
                ["audi", "bmw", "european", "fiat", "mercedes", "peugeot", "porsche", "renault", "volkswagen"],
                1
            )
        case .repetitiveGames:
            return (
                [
                    "adventure game", "backtrack", "backtracking", "dungeon", "game",
                    "games", "level design", "metroidvania", "platform", "repetitive",
                    "respawn", "rpg"
                ],
                ["backtracking", "level design", "metroidvania", "repetitive"],
                1
            )
        case .rawVegan:
            return (
                [
                    "cooked", "cuisine", "diet", "fresh", "fruit", "plant based", "raw",
                    "raw vegan", "salad", "sprout", "uncooked", "unprocessed", "vegan",
                    "vegetable"
                ],
                ["plant based", "raw", "raw vegan", "uncooked", "unprocessed"],
                2
            )
        case .restaurantQuality:
            return (
                [
                    "dining", "gimmick", "gimmicky", "menu", "quality", "restaurant",
                    "restaurants", "service", "trend", "trendy"
                ],
                ["gimmick", "gimmicky", "quality", "restaurant", "service"],
                2
            )
        case .spicyFood:
            return (
                [
                    "chili", "chilli", "curry", "hot pepper", "pepper", "sichuan",
                    "spice", "spices", "spicy"
                ],
                ["chili", "curry", "pepper", "sichuan", "spicy"],
                1
            )
        case .vegan:
            return (
                [
                    "animal", "animal derived", "butter", "cheese", "dairy", "egg", "eggs",
                    "fish", "honey", "meat", "milk", "plant based", "vegan", "vegetarian"
                ],
                ["animal derived", "dairy", "egg", "honey", "meat", "milk", "vegan"],
                1
            )
        case .shelterPets:
            return (
                [
                    "adopt", "adoption", "animal shelter", "breed", "breeder", "breeders",
                    "cat", "dog", "pet", "pet store", "pets", "rabbit", "rescue", "shelter"
                ],
                ["adopt", "adoption", "animal shelter", "breeder", "pet store", "rescue", "shelter"],
                1
            )
        case .textureSensitive:
            return (
                [
                    "blend", "clothing", "fabric", "itchy", "knit", "scratchy", "synthetic",
                    "texture", "textures", "wool"
                ],
                ["fabric", "itchy", "scratchy", "synthetic", "texture", "wool"],
                1
            )
        case .generic:
            return ([], [], 2)
        }
    }
}

private enum InstructionGenerator {
    static func instruction(for signal: PreferenceSignal, chunk: DocumentChunk, matchedTerms: [String]) -> String {
        let focus = matchedTerms.prefix(3).joined(separator: ", ")
        switch signal.kind {
        case .electricVehicles:
            return "When answering vehicle questions, use this chunk to prioritize fully electric options and exclude gas-powered choices; focus on \(focus)."
        case .pickupTrucks:
            return "Use this chunk as cautionary context for pickup trucks, towing, and oversized vehicles; steer recommendations toward practical non-pickup alternatives."
        case .europeanCars:
            return "Use this chunk to identify European car-brand content that should be de-emphasized or avoided for this user."
        case .repetitiveGames:
            return "Use this chunk only when it helps assess backtracking, repetition, or level-design friction in games."
        case .rawVegan:
            return "Use this chunk to preserve raw vegan constraints; surface uncooked, unprocessed, plant-based details and avoid cooked or animal-derived foods."
        case .restaurantQuality:
            return "Use this chunk to separate food and service quality from trendy or gimmicky dining signals."
        case .spicyFood:
            return "Use this chunk to detect spicy ingredients or regional cuisines that may conflict with the user's low-spice preference."
        case .vegan:
            return "Use this chunk to enforce strict vegan constraints, especially animal-derived ingredients such as dairy, eggs, honey, meat, or fish."
        case .shelterPets:
            return "Use this chunk to favor adoption, rescue, and shelter pathways over breeders or pet stores."
        case .textureSensitive:
            return "Use this chunk to flag scratchy fabrics, wool, and irritating synthetic blends while favoring softer clothing materials."
        case .generic:
            return "Use this chunk only when it directly supports the stated user preference; matched terms: \(focus)."
        }
    }
}
