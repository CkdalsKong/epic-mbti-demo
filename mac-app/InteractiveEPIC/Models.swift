import Foundation

struct PersonaPreset: Identifiable, Codable, Hashable {
    let personaIndex: Int
    let preferenceBlocks: [PreferenceBlock]

    var id: Int { personaIndex }

    enum CodingKeys: String, CodingKey {
        case personaIndex = "persona_index"
        case preferenceBlocks = "preference_blocks"
    }
}

struct PreferenceBlock: Identifiable, Codable, Hashable {
    let id: UUID
    let preference: String
    let queries: [PreferenceQuery]

    init(preference: String, queries: [PreferenceQuery]) {
        self.id = UUID()
        self.preference = preference
        self.queries = queries
    }

    enum CodingKeys: String, CodingKey {
        case preference
        case queries
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        id = UUID()
        preference = try container.decode(String.self, forKey: .preference)
        queries = try container.decode([PreferenceQuery].self, forKey: .queries)
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(preference, forKey: .preference)
        try container.encode(queries, forKey: .queries)
    }
}

struct PreferenceQuery: Codable, Hashable {
    let question: String
}

struct WikipediaResult: Identifiable, Hashable {
    let pageID: Int
    let title: String
    let snippet: String
    let wordCount: Int

    var id: Int { pageID }
}

struct WikiArticle: Identifiable, Hashable {
    let pageID: Int
    let title: String
    let extract: String
    let source: ArticleSource

    var id: Int { pageID }
    var wordCount: Int { TextTools.tokensIncludingShortWords(extract).count }
}

enum ArticleSource: String, Hashable {
    case wikipedia = "Wikipedia"
    case sample = "Sample"
}

struct DocumentChunk: Identifiable, Hashable {
    let id: UUID
    let articleTitle: String
    let index: Int
    let text: String
    let wordCount: Int

    init(articleTitle: String, index: Int, text: String) {
        self.id = UUID()
        self.articleTitle = articleTitle
        self.index = index
        self.text = text
        self.wordCount = TextTools.tokensIncludingShortWords(text).count
    }

    var byteCount: Int {
        text.utf8.count
    }

    var preview: String {
        text.collapsedWhitespace.prefixText(220)
    }
}

struct ExistingMemoryEntry: Identifiable, Hashable {
    let id = UUID()
    let chunk: DocumentChunk

    var approximateBytes: Int {
        chunk.byteCount + MemoryModel.rawChunkIndexOverhead
    }
}

struct PreferenceMatch: Identifiable, Hashable {
    let id = UUID()
    let preferenceIndex: Int
    let preference: String
    let kind: PreferenceKind
    let score: Double
    let matchedTerms: [String]
}

struct CoarseCandidate: Identifiable, Hashable {
    let id = UUID()
    let chunk: DocumentChunk
    let matches: [PreferenceMatch]

    var topScore: Double {
        matches.map(\.score).max() ?? 0
    }

    var topTerms: String {
        Array(matches.flatMap(\.matchedTerms).prefix(5)).joined(separator: ", ")
    }
}

struct FineEvaluation: Identifiable, Hashable {
    let id = UUID()
    let chunk: DocumentChunk
    let candidateMatches: [PreferenceMatch]
    let keptEntries: [EPICMemoryEntry]
    let rejectedReason: String?

    var isKept: Bool {
        !keptEntries.isEmpty
    }
}

struct EPICMemoryEntry: Identifiable, Hashable {
    let id = UUID()
    let chunk: DocumentChunk
    let preferenceIndex: Int
    let preference: String
    let kind: PreferenceKind
    let instruction: String
    let rationale: String
    let matchedTerms: [String]

    var approximateBytes: Int {
        chunk.byteCount + instruction.utf8.count + MemoryModel.instructionIndexOverhead
    }
}

enum PreferenceKind: String, CaseIterable, Hashable {
    case electricVehicles
    case pickupTrucks
    case europeanCars
    case repetitiveGames
    case rawVegan
    case restaurantQuality
    case spicyFood
    case vegan
    case shelterPets
    case textureSensitive
    case generic

    var label: String {
        switch self {
        case .electricVehicles: "EV only"
        case .pickupTrucks: "No pickups"
        case .europeanCars: "No European cars"
        case .repetitiveGames: "Avoid backtracking"
        case .rawVegan: "Raw vegan"
        case .restaurantQuality: "Quality dining"
        case .spicyFood: "No spicy food"
        case .vegan: "Strict vegan"
        case .shelterPets: "Adopt pets"
        case .textureSensitive: "Soft textures"
        case .generic: "Preference"
        }
    }

    var symbolName: String {
        switch self {
        case .electricVehicles: "bolt.car"
        case .pickupTrucks: "truck.box"
        case .europeanCars: "car"
        case .repetitiveGames: "gamecontroller"
        case .rawVegan: "leaf"
        case .restaurantQuality: "fork.knife"
        case .spicyFood: "flame"
        case .vegan: "leaf.circle"
        case .shelterPets: "house"
        case .textureSensitive: "tshirt"
        case .generic: "person.crop.circle"
        }
    }

    static func inferred(from preference: String) -> PreferenceKind {
        let text = TextTools.normalized(preference)
        if text.contains("electric vehicles") { return .electricVehicles }
        if text.contains("pickup trucks") { return .pickupTrucks }
        if text.contains("european car brands") { return .europeanCars }
        if text.contains("backtracking") { return .repetitiveGames }
        if text.contains("raw vegan") { return .rawVegan }
        if text.contains("gimmicky") { return .restaurantQuality }
        if text.contains("spicy food") { return .spicyFood }
        if text.contains("strict vegan") || text.contains("animal derived") { return .vegan }
        if text.contains("shelters") || text.contains("breeders") { return .shelterPets }
        if text.contains("scratchy") || text.contains("wool") { return .textureSensitive }
        return .generic
    }
}

enum MemoryModel {
    static let rawChunkIndexOverhead = 3_072
    static let instructionIndexOverhead = 768
}

enum EPICRunPhase: String, Hashable {
    case idle
    case preparing
    case embedding
    case coarseFiltering
    case chunkVerification
    case fineVerification
    case instructionIndexing
    case completed
    case failed
}

enum EPICChunkProgressState: String, Hashable {
    case pending
    case embedding
    case coarseCandidate
    case filteredOut
    case fineVerifying
    case fineDiscard
    case fineKeep
}

struct EPICChunkProgress: Hashable {
    var state: EPICChunkProgressState
    var detail: String
    var score: Double?

    static let pending = EPICChunkProgress(
        state: .pending,
        detail: "Waiting",
        score: nil
    )
}

struct EPICRunProgress: Hashable {
    var phase: EPICRunPhase
    var message: String
    var fraction: Double
    var processedChunks: Int
    var totalChunks: Int
    var completedFine: Int
    var totalFine: Int

    static let idle = EPICRunProgress(
        phase: .idle,
        message: "Waiting to run EPIC.",
        fraction: 0,
        processedChunks: 0,
        totalChunks: 0,
        completedFine: 0,
        totalFine: 0
    )
}

struct PipelineStats {
    let chunkCount: Int
    let existingEntryCount: Int
    let epicEntryCount: Int
    let existingBytes: Int
    let epicBytes: Int
    let coarseCount: Int
    let fineKeptChunkCount: Int
    let fineRejectedChunkCount: Int

    var savedBytes: Int {
        max(existingBytes - epicBytes, 0)
    }

    var reductionRatio: Double {
        guard epicBytes > 0 else { return 0 }
        return Double(existingBytes) / Double(epicBytes)
    }

    var reductionText: String {
        guard existingBytes > 0 else { return "Pending" }
        guard epicBytes > 0 else { return "Waiting for EPIC" }
        return String(format: "%.1fx smaller", reductionRatio)
    }
}
