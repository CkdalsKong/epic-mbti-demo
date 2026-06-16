import Foundation

enum RealEPICRuntimeError: LocalizedError {
    case missingHelper
    case missingPython
    case preloadedRuntimeUnavailable
    case failed(String)
    case invalidOutput

    var errorDescription: String? {
        switch self {
        case .missingHelper:
            "EPIC runtime helper script was not found."
        case .missingPython:
            "Local Python runtime was not found."
        case .preloadedRuntimeUnavailable:
            "Can't reach the EPIC demo server at http://127.0.0.1:8765. " +
            "Make sure the SSH tunnel to the GPU server is open and " +
            "epic_demo_server.py is running there (see server/README.md)."
        case .failed(let message):
            message
        case .invalidOutput:
            "EPIC runtime returned an unexpected response."
        }
    }
}

struct RealEPICFootprint: Codable, Hashable {
    let embeddingModel: String
    let embeddingDimension: Int
    let embeddingNormalized: Bool
    let threshold: Double
    let vectorIndex: String
    let llm: String
    let llmModelPath: String
    let existingTextBytes: Int
    let existingFaissIndexBytes: Int
    let existingTotalBytes: Int
    let epicChunkTextBytes: Int
    let epicInstructionBytes: Int
    let epicFaissIndexBytes: Int
    let epicTotalBytes: Int
    let instructionCount: Int

    enum CodingKeys: String, CodingKey {
        case embeddingModel = "embedding_model"
        case embeddingDimension = "embedding_dimension"
        case embeddingNormalized = "embedding_normalized"
        case threshold
        case vectorIndex = "vector_index"
        case llm
        case llmModelPath = "llm_model_path"
        case existingTextBytes = "existing_text_bytes"
        case existingFaissIndexBytes = "existing_faiss_index_bytes"
        case existingTotalBytes = "existing_total_bytes"
        case epicChunkTextBytes = "epic_chunk_text_bytes"
        case epicInstructionBytes = "epic_instruction_bytes"
        case epicFaissIndexBytes = "epic_faiss_index_bytes"
        case epicTotalBytes = "epic_total_bytes"
        case instructionCount = "instruction_count"
    }
}

struct RealEPICResult: Codable {
    let runtime: RealEPICFootprint
    let coarseCandidates: [RuntimeCoarseCandidate]
    let fineEvaluations: [RuntimeFineEvaluation]

    enum CodingKeys: String, CodingKey {
        case runtime
        case coarseCandidates = "coarse_candidates"
        case fineEvaluations = "fine_evaluations"
    }
}

nonisolated struct RuntimeProgressEvent: Codable {
    let event: String
    let message: String?
    let chunkIndex: Int?
    let processedChunks: Int?
    let totalChunks: Int?
    let totalPreferences: Int?
    let candidateCount: Int?
    let completedFine: Int?
    let totalFine: Int?
    let instructionCount: Int?
    let threshold: Double?
    let existingFaissIndexBytes: Int?
    let coarseCandidate: RuntimeCoarseCandidate?
    let fineEvaluation: RuntimeFineEvaluation?
    let result: RealEPICResult?
    let error: String?
    let errorType: String?

    enum CodingKeys: String, CodingKey {
        case event
        case message
        case chunkIndex = "chunk_index"
        case processedChunks = "processed_chunks"
        case totalChunks = "total_chunks"
        case totalPreferences = "total_preferences"
        case candidateCount = "candidate_count"
        case completedFine = "completed_fine"
        case totalFine = "total_fine"
        case instructionCount = "instruction_count"
        case threshold
        case existingFaissIndexBytes = "existing_faiss_index_bytes"
        case coarseCandidate = "coarse_candidate"
        case fineEvaluation = "fine_evaluation"
        case result
        case error
        case errorType = "error_type"
    }
}

private struct RuntimeErrorResponse: Codable {
    let error: String
    let type: String?
}

struct RuntimeCoarseCandidate: Codable {
    let chunkIndex: Int
    let matches: [RuntimePreferenceMatch]

    enum CodingKeys: String, CodingKey {
        case chunkIndex = "chunk_index"
        case matches
    }
}

struct RuntimePreferenceMatch: Codable {
    let preferenceIndex: Int
    let preference: String
    let kind: String
    let score: Double
    let matchedTerms: [String]

    enum CodingKeys: String, CodingKey {
        case preferenceIndex = "preference_index"
        case preference
        case kind
        case score
        case matchedTerms = "matched_terms"
    }
}

struct RuntimeFineEvaluation: Codable {
    let chunkIndex: Int
    let candidateMatches: [RuntimePreferenceMatch]
    let keptEntries: [RuntimeEPICMemoryEntry]
    let rejectedReason: String?

    enum CodingKeys: String, CodingKey {
        case chunkIndex = "chunk_index"
        case candidateMatches = "candidate_matches"
        case keptEntries = "kept_entries"
        case rejectedReason = "rejected_reason"
    }
}

struct RuntimeEPICMemoryEntry: Codable {
    let chunkIndex: Int
    let preferenceIndex: Int
    let preference: String
    let kind: String
    let instruction: String
    let rationale: String
    let matchedTerms: [String]

    enum CodingKeys: String, CodingKey {
        case chunkIndex = "chunk_index"
        case preferenceIndex = "preference_index"
        case preference
        case kind
        case instruction
        case rationale
        case matchedTerms = "matched_terms"
    }
}

private struct RuntimeInput: Codable {
    let threshold: Double
    let chunks: [RuntimeInputChunk]
    let preferences: [RuntimeInputPreference]
}

private struct RuntimeInputChunk: Codable {
    let index: Int
    let articleTitle: String
    let text: String

    enum CodingKeys: String, CodingKey {
        case index
        case articleTitle = "article_title"
        case text
    }
}

private struct RuntimeInputPreference: Codable {
    let index: Int
    let preference: String
}

final class RealEPICRuntime {
    private let pythonPath = "/Users/jam/miniconda3/envs/epic/bin/python3.11"
    private let llmModel = "Qwen/Qwen3-8B"
    private let llmServerURLString = "http://127.0.0.1:8008"
    private let preloadedRuntimeURL = URL(string: "http://127.0.0.1:8765")!

    func run(chunks: [DocumentChunk], persona: PersonaPreset, threshold: Double) async throws -> RealEPICResult {
        let helperURL = helperScriptURL()
        guard FileManager.default.fileExists(atPath: helperURL.path) else {
            throw RealEPICRuntimeError.missingHelper
        }
        guard FileManager.default.fileExists(atPath: pythonPath) else {
            throw RealEPICRuntimeError.missingPython
        }

        let input = RuntimeInput(
            threshold: threshold,
            chunks: chunks.map {
                RuntimeInputChunk(index: $0.index, articleTitle: $0.articleTitle, text: $0.text)
            },
            preferences: persona.preferenceBlocks.enumerated().map {
                RuntimeInputPreference(index: $0.offset, preference: $0.element.preference)
            }
        )
        let inputData = try JSONEncoder().encode(input)

        let pythonPath = pythonPath
        let llmModel = llmModel
        let llmServerURLString = llmServerURLString
        let processOutput = try await Task.detached(priority: .userInitiated) {
            try RealEPICRuntime.runProcess(
                pythonPath: pythonPath,
                llmModel: llmModel,
                llmServerURLString: llmServerURLString,
                helperURL: helperURL,
                inputData: inputData
            )
        }.value

        if processOutput.terminationStatus != 0 {
            if let runtimeError = try? JSONDecoder().decode(RuntimeErrorResponse.self, from: processOutput.outputData) {
                throw RealEPICRuntimeError.failed(runtimeError.error)
            }
            let stderr = String(data: processOutput.stderrData, encoding: .utf8) ?? ""
            let stdout = String(data: processOutput.outputData, encoding: .utf8) ?? ""
            throw RealEPICRuntimeError.failed(stderr.isEmpty ? stdout : stderr)
        }

        do {
            return try JSONDecoder().decode(RealEPICResult.self, from: processOutput.outputData)
        } catch {
            throw RealEPICRuntimeError.invalidOutput
        }
    }

    func runStreaming(
        chunks: [DocumentChunk],
        persona: PersonaPreset,
        threshold: Double,
        onEvent: @escaping @Sendable (RuntimeProgressEvent) async -> Void
    ) async throws -> RealEPICResult {
        guard try await Self.preloadedRuntimeIsAvailable(baseURL: preloadedRuntimeURL) else {
            throw RealEPICRuntimeError.preloadedRuntimeUnavailable
        }

        let input = RuntimeInput(
            threshold: threshold,
            chunks: chunks.map {
                RuntimeInputChunk(index: $0.index, articleTitle: $0.articleTitle, text: $0.text)
            },
            preferences: persona.preferenceBlocks.enumerated().map {
                RuntimeInputPreference(index: $0.offset, preference: $0.element.preference)
            }
        )
        let inputData = try JSONEncoder().encode(input)
        return try await Self.runStreamingServerRequest(
            baseURL: preloadedRuntimeURL,
            inputData: inputData,
            onEvent: onEvent
        )
    }

    func runStreamingProcessFallback(
        chunks: [DocumentChunk],
        persona: PersonaPreset,
        threshold: Double,
        onEvent: @escaping @Sendable (RuntimeProgressEvent) async -> Void
    ) async throws -> RealEPICResult {
        let helperURL = helperScriptURL()
        guard FileManager.default.fileExists(atPath: helperURL.path) else {
            throw RealEPICRuntimeError.missingHelper
        }
        guard FileManager.default.fileExists(atPath: pythonPath) else {
            throw RealEPICRuntimeError.missingPython
        }

        let input = RuntimeInput(
            threshold: threshold,
            chunks: chunks.map {
                RuntimeInputChunk(index: $0.index, articleTitle: $0.articleTitle, text: $0.text)
            },
            preferences: persona.preferenceBlocks.enumerated().map {
                RuntimeInputPreference(index: $0.offset, preference: $0.element.preference)
            }
        )
        let inputData = try JSONEncoder().encode(input)

        let pythonPath = pythonPath
        let llmModel = llmModel
        let llmServerURLString = llmServerURLString
        return try await Task.detached(priority: .userInitiated) {
            try await RealEPICRuntime.runStreamingProcess(
                pythonPath: pythonPath,
                llmModel: llmModel,
                llmServerURLString: llmServerURLString,
                helperURL: helperURL,
                inputData: inputData,
                onEvent: onEvent
            )
        }.value
    }

    nonisolated private static func preloadedRuntimeIsAvailable(baseURL: URL) async throws -> Bool {
        var healthURL = baseURL
        healthURL.append(path: "health")
        var request = URLRequest(url: healthURL)
        request.timeoutInterval = 1.2

        do {
            let (_, response) = try await URLSession.shared.data(for: request)
            guard let httpResponse = response as? HTTPURLResponse else { return false }
            return (200..<300).contains(httpResponse.statusCode)
        } catch {
            return false
        }
    }

    nonisolated private static func runProcess(
        pythonPath: String,
        llmModel: String,
        llmServerURLString: String,
        helperURL: URL,
        inputData: Data
    ) throws -> (terminationStatus: Int32, outputData: Data, stderrData: Data) {
        let process = Process()
        process.executableURL = URL(fileURLWithPath: pythonPath)
        process.arguments = [
            helperURL.path,
            "--llm-server-url",
            llmServerURLString,
            "--llm-model",
            llmModel,
        ]
        process.environment = ProcessInfo.processInfo.environment.merging([
            "TOKENIZERS_PARALLELISM": "false",
        ]) { _, new in new }

        let stdinPipe = Pipe()
        let stdoutPipe = Pipe()
        let stderrPipe = Pipe()
        process.standardInput = stdinPipe
        process.standardOutput = stdoutPipe
        process.standardError = stderrPipe

        try process.run()
        stdinPipe.fileHandleForWriting.write(inputData)
        stdinPipe.fileHandleForWriting.closeFile()
        process.waitUntilExit()

        let outputData = stdoutPipe.fileHandleForReading.readDataToEndOfFile()
        let stderrData = stderrPipe.fileHandleForReading.readDataToEndOfFile()

        return (process.terminationStatus, outputData, stderrData)
    }

    nonisolated private static func runStreamingProcess(
        pythonPath: String,
        llmModel: String,
        llmServerURLString: String,
        helperURL: URL,
        inputData: Data,
        onEvent: @escaping @Sendable (RuntimeProgressEvent) async -> Void
    ) async throws -> RealEPICResult {
        let process = Process()
        process.executableURL = URL(fileURLWithPath: pythonPath)
        process.arguments = [
            helperURL.path,
            "--llm-server-url",
            llmServerURLString,
            "--llm-model",
            llmModel,
            "--events",
        ]
        process.environment = ProcessInfo.processInfo.environment.merging([
            "TOKENIZERS_PARALLELISM": "false",
        ]) { _, new in new }

        let stdinPipe = Pipe()
        let stdoutPipe = Pipe()
        let stderrPipe = Pipe()
        process.standardInput = stdinPipe
        process.standardOutput = stdoutPipe
        process.standardError = stderrPipe

        try process.run()
        stdinPipe.fileHandleForWriting.write(inputData)
        stdinPipe.fileHandleForWriting.closeFile()

        let stderrTask = Task.detached(priority: .utility) {
            stderrPipe.fileHandleForReading.readDataToEndOfFile()
        }

        let decoder = JSONDecoder()
        var finalResult: RealEPICResult?
        var runtimeError: RuntimeErrorResponse?
        var stdoutLog = ""

        for try await line in stdoutPipe.fileHandleForReading.bytes.lines {
            let trimmedLine = line.trimmingCharacters(in: .whitespacesAndNewlines)
            guard !trimmedLine.isEmpty else { continue }
            stdoutLog += trimmedLine + "\n"

            guard let lineData = trimmedLine.data(using: .utf8) else { continue }
            guard let event = try? decoder.decode(RuntimeProgressEvent.self, from: lineData) else {
                continue
            }

            if event.event == "error" {
                runtimeError = RuntimeErrorResponse(
                    error: event.error ?? "EPIC runtime failed.",
                    type: event.errorType
                )
            }
            if event.event == "complete", let result = event.result {
                finalResult = result
            }
            await onEvent(event)
        }

        process.waitUntilExit()
        let stderrData = await stderrTask.value

        if process.terminationStatus != 0 {
            if let runtimeError {
                throw RealEPICRuntimeError.failed(runtimeError.error)
            }
            let stderr = String(data: stderrData, encoding: .utf8) ?? ""
            throw RealEPICRuntimeError.failed(stderr.isEmpty ? stdoutLog : stderr)
        }

        guard let finalResult else {
            if let runtimeError {
                throw RealEPICRuntimeError.failed(runtimeError.error)
            }
            throw RealEPICRuntimeError.invalidOutput
        }
        return finalResult
    }

    nonisolated private static func runStreamingServerRequest(
        baseURL: URL,
        inputData: Data,
        onEvent: @escaping @Sendable (RuntimeProgressEvent) async -> Void
    ) async throws -> RealEPICResult {
        var runURL = baseURL
        runURL.append(path: "run")
        var request = URLRequest(url: runURL)
        request.httpMethod = "POST"
        request.timeoutInterval = 600
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = inputData

        let (bytes, response) = try await URLSession.shared.bytes(for: request)
        guard let httpResponse = response as? HTTPURLResponse else {
            throw RealEPICRuntimeError.invalidOutput
        }
        guard (200..<300).contains(httpResponse.statusCode) else {
            throw RealEPICRuntimeError.failed("Preloaded EPIC runtime returned HTTP \(httpResponse.statusCode).")
        }

        let decoder = JSONDecoder()
        var finalResult: RealEPICResult?
        var runtimeError: RuntimeErrorResponse?

        for try await line in bytes.lines {
            let trimmedLine = line.trimmingCharacters(in: .whitespacesAndNewlines)
            guard !trimmedLine.isEmpty else { continue }
            guard let lineData = trimmedLine.data(using: .utf8) else { continue }
            guard let event = try? decoder.decode(RuntimeProgressEvent.self, from: lineData) else {
                continue
            }

            if event.event == "error" {
                runtimeError = RuntimeErrorResponse(
                    error: event.error ?? "EPIC runtime failed.",
                    type: event.errorType
                )
            }
            if event.event == "complete", let result = event.result {
                finalResult = result
            }
            await onEvent(event)
        }

        if let runtimeError {
            throw RealEPICRuntimeError.failed(runtimeError.error)
        }
        guard let finalResult else {
            throw RealEPICRuntimeError.invalidOutput
        }
        return finalResult
    }

    private func helperScriptURL() -> URL {
        if let bundled = Bundle.main.url(forResource: "epic_runtime", withExtension: "py") {
            return bundled
        }
        return URL(fileURLWithPath: "/Users/jam/Desktop/InteractiveEPIC/InteractiveEPIC/epic_runtime.py")
    }
}
