import Foundation

// ── Models ────────────────────────────────────────────────────────────────

struct RetrievedDoc: Codable, Identifiable, Hashable {
    let id: UUID
    let chunkText: String
    let articleTitle: String
    let instruction: String?   // EPIC only
    let preference: String?    // EPIC only
    let score: Double

    init(chunkText: String, articleTitle: String, instruction: String? = nil, preference: String? = nil, score: Double) {
        self.id = UUID()
        self.chunkText = chunkText
        self.articleTitle = articleTitle
        self.instruction = instruction
        self.preference = preference
        self.score = score
    }

    enum CodingKeys: String, CodingKey {
        case chunkText = "chunk_text"
        case articleTitle = "article_title"
        case instruction
        case preference
        case score
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = UUID()
        chunkText = try c.decode(String.self, forKey: .chunkText)
        articleTitle = try c.decode(String.self, forKey: .articleTitle)
        instruction = try c.decodeIfPresent(String.self, forKey: .instruction)
        preference = try c.decodeIfPresent(String.self, forKey: .preference)
        score = try c.decode(Double.self, forKey: .score)
    }

    func encode(to encoder: Encoder) throws {
        var c = encoder.container(keyedBy: CodingKeys.self)
        try c.encode(chunkText, forKey: .chunkText)
        try c.encode(articleTitle, forKey: .articleTitle)
        try c.encodeIfPresent(instruction, forKey: .instruction)
        try c.encodeIfPresent(preference, forKey: .preference)
        try c.encode(score, forKey: .score)
    }
}

struct MetricResult: Codable, Hashable {
    let acknow: Bool
    let violate: Bool
    let hallucinate: Bool
    let helpful: Bool
    let preferenceFollowing: Bool

    enum CodingKeys: String, CodingKey {
        case acknow, violate, hallucinate, helpful
        case preferenceFollowing = "preference_following"
    }
}

struct EvaluationResult: Hashable {
    let epic: MetricResult
    let rag: MetricResult
}

// ── Events from /generate ────────────────────────────────────────────────

nonisolated struct GenerateProgressEvent: Codable {
    let event: String
    let text: String?
    let epicDocs: [RetrievedDoc]?
    let ragDocs: [RetrievedDoc]?
    let epicResponse: String?
    let ragResponse: String?
    let topPreference: String?
    let error: String?
    // Retrieval latency (ms) and index sizes (bytes)
    let epicRetrMs: Double?
    let ragRetrMs: Double?
    let epicIndexBytes: Int?
    let ragIndexBytes: Int?
    let epicEntries: Int?
    let ragChunks: Int?

    enum CodingKeys: String, CodingKey {
        case event, text, error
        case epicDocs = "epic_docs"
        case ragDocs = "rag_docs"
        case epicResponse = "epic_response"
        case ragResponse = "rag_response"
        case topPreference = "top_preference"
        case epicRetrMs = "epic_retr_ms"
        case ragRetrMs = "rag_retr_ms"
        case epicIndexBytes = "epic_index_bytes"
        case ragIndexBytes = "rag_index_bytes"
        case epicEntries = "epic_entries"
        case ragChunks = "rag_chunks"
    }
}

// ── Runtime errors ────────────────────────────────────────────────────────

enum GenerationRuntimeError: LocalizedError {
    case serverUnavailable
    case noSession
    case failed(String)

    var errorDescription: String? {
        switch self {
        case .serverUnavailable: "EPIC Demo Server is not running at localhost:8766."
        case .noSession: "No indexed session. Run EPIC indexing first."
        case .failed(let m): m
        }
    }
}

// ── GenerationRuntime ─────────────────────────────────────────────────────

final class GenerationRuntime {
    private let baseURL = URL(string: "http://127.0.0.1:8766")!

    // ── Generate (streaming) ──────────────────────────────────────────────

    func generate(
        question: String,
        topK: Int = 5,
        onEvent: @escaping @Sendable (GenerateProgressEvent) async -> Void
    ) async throws -> (epicResponse: String, ragResponse: String, epicDocs: [RetrievedDoc], ragDocs: [RetrievedDoc], topPreference: String) {
        let url = baseURL.appendingPathComponent("generate")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.timeoutInterval = 300
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let body: [String: Any] = ["question": question, "top_k": topK]
        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (bytes, response) = try await URLSession.shared.bytes(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw GenerationRuntimeError.failed("Invalid HTTP response.")
        }
        if http.statusCode == 400 {
            // No session or bad request
            throw GenerationRuntimeError.noSession
        }
        guard (200..<300).contains(http.statusCode) else {
            throw GenerationRuntimeError.failed("Server returned HTTP \(http.statusCode).")
        }

        let decoder = JSONDecoder()
        var epicResponse = ""
        var ragResponse = ""
        var epicDocs: [RetrievedDoc] = []
        var ragDocs: [RetrievedDoc] = []
        var topPreference = ""

        for try await line in bytes.lines {
            let trimmed = line.trimmingCharacters(in: .whitespacesAndNewlines)
            guard !trimmed.isEmpty, let data = trimmed.data(using: .utf8) else { continue }
            guard let event = try? decoder.decode(GenerateProgressEvent.self, from: data) else { continue }

            switch event.event {
            case "retrieved":
                epicDocs = event.epicDocs ?? []
                ragDocs = event.ragDocs ?? []
                await onEvent(event)

            case "epic_token":
                if let text = event.text {
                    epicResponse += text
                }
                await onEvent(event)

            case "rag_token":
                if let text = event.text {
                    ragResponse += text
                }
                await onEvent(event)

            case "complete":
                epicResponse = event.epicResponse ?? epicResponse
                ragResponse = event.ragResponse ?? ragResponse
                topPreference = event.topPreference ?? ""
                if let docs = event.epicDocs { epicDocs = docs }
                if let docs = event.ragDocs { ragDocs = docs }
                await onEvent(event)

            case "error":
                throw GenerationRuntimeError.failed(event.error ?? "Unknown generate error.")

            default:
                await onEvent(event)
            }
        }

        return (epicResponse, ragResponse, epicDocs, ragDocs, topPreference)
    }

    // ── Evaluate (non-streaming) ──────────────────────────────────────────

    func evaluate(
        question: String,
        preference: String,
        epicResponse: String,
        ragResponse: String
    ) async throws -> EvaluationResult {
        let url = baseURL.appendingPathComponent("evaluate")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.timeoutInterval = 300
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let body: [String: Any] = [
            "question": question,
            "preference": preference,
            "epic_response": epicResponse,
            "rag_response": ragResponse,
        ]
        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw GenerationRuntimeError.failed("Invalid HTTP response.")
        }
        guard (200..<300).contains(http.statusCode) else {
            let msg = (try? JSONSerialization.jsonObject(with: data) as? [String: Any])?["error"] as? String ?? "HTTP \(http.statusCode)"
            throw GenerationRuntimeError.failed(msg)
        }

        struct EvalPayload: Codable {
            let epic: MetricResult
            let rag: MetricResult
        }
        let payload = try JSONDecoder().decode(EvalPayload.self, from: data)
        return EvaluationResult(epic: payload.epic, rag: payload.rag)
    }

    // ── Retrieval-only (no generation) ──────────────────────────────────────

    struct RetrieveOnlyResult {
        let epicDocs: [RetrievedDoc]
        let ragDocs: [RetrievedDoc]
        let embedMs: Double          // shared query-embedding step
        let steerMs: Double          // EPIC-only: fold top-1 preference into the query vector
        let matchedPreference: String?
        let steerScore: Double
        let epicSearchMs: Double     // EPIC instruction index search (with steered vector)
        let ragSearchMs: Double      // RAG chunk index search (raw vector)
        let epicRetrMs: Double       // embed + steer + epicSearch (total)
        let ragRetrMs: Double        // embed + ragSearch (total)
        let epicIndexBytes: Int
        let ragIndexBytes: Int
        let epicEntries: Int
        let ragChunks: Int
    }

    func retrieveOnly(question: String, topK: Int = 5) async throws -> RetrieveOnlyResult {
        let url = baseURL.appendingPathComponent("retrieve")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.timeoutInterval = 60
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: ["question": question, "top_k": topK])

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw GenerationRuntimeError.failed("Invalid HTTP response.")
        }
        if http.statusCode == 400 {
            throw GenerationRuntimeError.noSession
        }
        guard (200..<300).contains(http.statusCode) else {
            let msg = (try? JSONSerialization.jsonObject(with: data) as? [String: Any])?["error"] as? String ?? "HTTP \(http.statusCode)"
            throw GenerationRuntimeError.failed(msg)
        }

        struct Payload: Codable {
            let epicDocs: [RetrievedDoc]
            let ragDocs: [RetrievedDoc]
            let embedMs: Double
            let steerMs: Double
            let matchedPreference: String?
            let steerScore: Double
            let epicSearchMs: Double
            let ragSearchMs: Double
            let epicRetrMs: Double
            let ragRetrMs: Double
            let epicIndexBytes: Int
            let ragIndexBytes: Int
            let epicEntries: Int
            let ragChunks: Int

            enum CodingKeys: String, CodingKey {
                case epicDocs = "epic_docs", ragDocs = "rag_docs"
                case embedMs = "embed_ms"
                case steerMs = "steer_ms", matchedPreference = "matched_preference", steerScore = "steer_score"
                case epicSearchMs = "epic_search_ms", ragSearchMs = "rag_search_ms"
                case epicRetrMs = "epic_retr_ms", ragRetrMs = "rag_retr_ms"
                case epicIndexBytes = "epic_index_bytes", ragIndexBytes = "rag_index_bytes"
                case epicEntries = "epic_entries", ragChunks = "rag_chunks"
            }
        }
        let p = try JSONDecoder().decode(Payload.self, from: data)
        return RetrieveOnlyResult(
            epicDocs: p.epicDocs, ragDocs: p.ragDocs,
            embedMs: p.embedMs,
            steerMs: p.steerMs, matchedPreference: p.matchedPreference, steerScore: p.steerScore,
            epicSearchMs: p.epicSearchMs, ragSearchMs: p.ragSearchMs,
            epicRetrMs: p.epicRetrMs, ragRetrMs: p.ragRetrMs,
            epicIndexBytes: p.epicIndexBytes, ragIndexBytes: p.ragIndexBytes,
            epicEntries: p.epicEntries, ragChunks: p.ragChunks
        )
    }

    // ── Load pre-built persona index ──────────────────────────────────────

    struct LoadPersonaResult {
        let personaIndex: Int
        let epicEntries: Int
        let ragChunks: Int
        let epicIndexBytes: Int
        let ragIndexBytes: Int
    }

    func loadPersona(index: Int) async throws -> LoadPersonaResult {
        let url = baseURL.appendingPathComponent("load_persona")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.timeoutInterval = 30
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: ["persona_index": index])

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw GenerationRuntimeError.failed("Invalid HTTP response.")
        }
        if http.statusCode == 404 {
            throw GenerationRuntimeError.failed("No pre-indexed data for persona \(index). Run preindex_corpus.py first.")
        }
        guard (200..<300).contains(http.statusCode) else {
            let msg = (try? JSONSerialization.jsonObject(with: data) as? [String: Any])?["error"] as? String ?? "HTTP \(http.statusCode)"
            throw GenerationRuntimeError.failed(msg)
        }
        let json = try JSONSerialization.jsonObject(with: data) as? [String: Any] ?? [:]
        return LoadPersonaResult(
            personaIndex: json["persona_index"] as? Int ?? index,
            epicEntries: json["epic_entries"] as? Int ?? 0,
            ragChunks: json["rag_chunks"] as? Int ?? 0,
            epicIndexBytes: json["epic_index_bytes"] as? Int ?? 0,
            ragIndexBytes: json["rag_index_bytes"] as? Int ?? 0
        )
    }

    // ── Health check ─────────────────────────────────────────────────────

    func isServerReady() async -> Bool {
        let url = baseURL.appendingPathComponent("health")
        var request = URLRequest(url: url)
        request.timeoutInterval = 1.5
        do {
            let (_, response) = try await URLSession.shared.data(for: request)
            return (response as? HTTPURLResponse).map { (200..<500).contains($0.statusCode) } ?? false
        } catch {
            return false
        }
    }
}
