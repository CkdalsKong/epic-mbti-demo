import Foundation

enum WikipediaServiceError: LocalizedError {
    case emptyQuery
    case missingExtract
    case invalidResponse

    var errorDescription: String? {
        switch self {
        case .emptyQuery:
            "Enter a Wikipedia topic."
        case .missingExtract:
            "Wikipedia returned no extract for the selected page."
        case .invalidResponse:
            "Wikipedia returned an unexpected response."
        }
    }
}

final class WikipediaService {
    func search(query: String) async throws -> [WikipediaResult] {
        let trimmed = query.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { throw WikipediaServiceError.emptyQuery }

        var components = URLComponents(string: "https://en.wikipedia.org/w/api.php")!
        components.queryItems = [
            URLQueryItem(name: "action", value: "query"),
            URLQueryItem(name: "list", value: "search"),
            URLQueryItem(name: "srsearch", value: trimmed),
            URLQueryItem(name: "srlimit", value: "8"),
            URLQueryItem(name: "format", value: "json"),
            URLQueryItem(name: "utf8", value: "1")
        ]

        let response: SearchResponse = try await request(components.url!)
        return response.query?.search.map {
            WikipediaResult(
                pageID: $0.pageid,
                title: $0.title,
                snippet: ($0.snippet ?? "").strippedHTML,
                wordCount: $0.wordcount ?? 0
            )
        } ?? []
    }

    func fetchArticle(pageID: Int) async throws -> WikiArticle {
        var components = URLComponents(string: "https://en.wikipedia.org/w/api.php")!
        components.queryItems = [
            URLQueryItem(name: "action", value: "query"),
            URLQueryItem(name: "prop", value: "extracts"),
            URLQueryItem(name: "explaintext", value: "1"),
            URLQueryItem(name: "exsectionformat", value: "plain"),
            URLQueryItem(name: "redirects", value: "1"),
            URLQueryItem(name: "pageids", value: String(pageID)),
            URLQueryItem(name: "format", value: "json"),
            URLQueryItem(name: "utf8", value: "1")
        ]

        let response: ExtractResponse = try await request(components.url!)
        guard let page = response.query.pages.values.first else {
            throw WikipediaServiceError.invalidResponse
        }
        guard let extract = page.extract?.collapsedWhitespace, !extract.isEmpty else {
            throw WikipediaServiceError.missingExtract
        }

        return WikiArticle(
            pageID: page.pageid ?? pageID,
            title: page.title,
            extract: extract,
            source: .wikipedia
        )
    }

    private func request<T: Decodable>(_ url: URL) async throws -> T {
        var request = URLRequest(url: url)
        request.setValue("InteractiveEPIC/1.0 (macOS demo; preference-aligned indexing)", forHTTPHeaderField: "User-Agent")
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse,
              (200..<300).contains(httpResponse.statusCode) else {
            throw WikipediaServiceError.invalidResponse
        }
        return try JSONDecoder().decode(T.self, from: data)
    }
}

private struct SearchResponse: Decodable {
    let query: SearchQuery?
}

private struct SearchQuery: Decodable {
    let search: [SearchItem]
}

private struct SearchItem: Decodable {
    let pageid: Int
    let title: String
    let snippet: String?
    let wordcount: Int?
}

private struct ExtractResponse: Decodable {
    let query: ExtractQuery
}

private struct ExtractQuery: Decodable {
    let pages: [String: ExtractPage]
}

private struct ExtractPage: Decodable {
    let pageid: Int?
    let title: String
    let extract: String?
}
