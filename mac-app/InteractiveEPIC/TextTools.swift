import Foundation

enum TextTools {
    static let stopWords: Set<String> = [
        "about", "above", "after", "again", "against", "also", "among", "because", "been",
        "being", "between", "cannot", "could", "does", "doing", "down", "during", "each",
        "from", "have", "into", "known", "latest", "like", "more", "most", "only", "options",
        "over", "past", "recommend", "recommended", "regardless", "should", "some", "strong",
        "strict", "strictly", "such", "than", "that", "their", "them", "there", "these",
        "they", "this", "those", "through", "under", "very", "what", "when", "where",
        "which", "while", "with", "without", "would", "years", "your"
    ]

    static func normalized(_ text: String) -> String {
        text
            .lowercased()
            .folding(options: [.diacriticInsensitive], locale: .current)
            .replacingOccurrences(of: "[^a-z0-9]+", with: " ", options: .regularExpression)
            .collapsedWhitespace
    }

    static func tokens(_ text: String) -> [String] {
        tokensIncludingShortWords(text)
            .filter { $0.count > 2 && !stopWords.contains($0) }
    }

    static func tokensIncludingShortWords(_ text: String) -> [String] {
        normalized(text)
            .split(separator: " ")
            .map(String.init)
    }

    static func contains(term: String, in normalizedText: String, tokenSet: Set<String>) -> Bool {
        let cleanTerm = normalized(term)
        guard !cleanTerm.isEmpty else { return false }
        if cleanTerm.contains(" ") {
            return " \(normalizedText) ".contains(" \(cleanTerm) ")
        }
        return tokenSet.contains(cleanTerm)
    }
}

extension String {
    var collapsedWhitespace: String {
        components(separatedBy: .whitespacesAndNewlines)
            .filter { !$0.isEmpty }
            .joined(separator: " ")
    }

    func prefixText(_ maxLength: Int) -> String {
        guard count > maxLength else { return self }
        let end = index(startIndex, offsetBy: maxLength)
        return String(self[..<end]).collapsedWhitespace + "..."
    }

    var strippedHTML: String {
        replacingOccurrences(of: "<[^>]+>", with: "", options: .regularExpression)
            .replacingOccurrences(of: "&quot;", with: "\"")
            .replacingOccurrences(of: "&amp;", with: "&")
            .replacingOccurrences(of: "&#039;", with: "'")
            .collapsedWhitespace
    }
}

extension Int {
    var memoryString: String {
        ByteCountFormatter.string(fromByteCount: Int64(self), countStyle: .memory)
    }
}
