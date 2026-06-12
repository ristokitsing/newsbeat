import Foundation

/// Which social draft to generate on demand.
enum PostKind: String, Codable, Sendable, CaseIterable, Identifiable {
    case linkedIn
    case instagram

    var id: String { rawValue }

    var title: String {
        switch self {
        case .linkedIn: "LinkedIn post"
        case .instagram: "Instagram carousel"
        }
    }

    var shortName: String {
        switch self {
        case .linkedIn: "LinkedIn"
        case .instagram: "Instagram"
        }
    }
}

/// A draft produced on demand by Claude and cached locally. Exactly one of the
/// payloads is populated, matching `kind`.
struct GeneratedPost: Codable, Sendable, Hashable {
    let kind: PostKind
    let linkedIn: LinkedInAngle?
    let instagram: InstagramCarousel?

    func text(url: URL) -> String {
        switch kind {
        case .linkedIn:
            guard let linkedIn else { return "" }
            return formatLinkedIn(
                hook: linkedIn.hook,
                points: linkedIn.points,
                url: url
            )
        case .instagram:
            guard let instagram else { return "" }
            return formatInstagram(
                slides: instagram.slides,
                cta: instagram.cta,
                url: url
            )
        }
    }
}

enum PostGenerationError: LocalizedError {
    case missingAPIKey
    case http(status: Int, message: String)
    case malformedResponse(String)

    var errorDescription: String? {
        switch self {
        case .missingAPIKey:
            "Add your Anthropic API key in Settings to generate posts."
        case let .http(status, message):
            "Claude API error (\(status)): \(message)"
        case let .malformedResponse(detail):
            "Could not read the generated post: \(detail)"
        }
    }
}

/// Calls the Anthropic Messages API directly (raw URLSession — no Swift SDK) to
/// generate LinkedIn/Instagram drafts from a feed item's summary. The request
/// body building and response parsing are pure static functions so they can be
/// unit-tested without the network.
actor PostGenerationService {
    static let defaultModel = "claude-haiku-4-5"
    private static let endpoint = URL(
        string: "https://api.anthropic.com/v1/messages"
    )!

    private let session: URLSession

    init(session: URLSession = .shared) {
        self.session = session
    }

    func generate(
        _ kind: PostKind,
        for item: DigestItem,
        apiKey: String,
        model: String
    ) async throws -> GeneratedPost {
        let key = apiKey.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !key.isEmpty else { throw PostGenerationError.missingAPIKey }

        var request = URLRequest(url: Self.endpoint)
        request.httpMethod = "POST"
        request.timeoutInterval = 30
        request.setValue(key, forHTTPHeaderField: "x-api-key")
        request.setValue("2023-06-01", forHTTPHeaderField: "anthropic-version")
        request.setValue("application/json", forHTTPHeaderField: "content-type")
        request.httpBody = try Self.requestBody(kind, for: item, model: model)

        let (data, response) = try await session.data(for: request)
        let status = (response as? HTTPURLResponse)?.statusCode ?? 0
        return try Self.parsePost(kind, data: data, statusCode: status)
    }

    // MARK: - Pure helpers (no network; unit-tested)

    static func requestBody(
        _ kind: PostKind,
        for item: DigestItem,
        model: String
    ) throws -> Data {
        let format: [String: Any] = [
            "type": "json_schema",
            "schema": try schema(for: kind),
        ]
        let outputConfig: [String: Any] = ["format": format]
        let messages: [[String: String]] = [
            ["role": "user", "content": userPrompt(kind, for: item)],
        ]
        let body: [String: Any] = [
            "model": model,
            "max_tokens": 1500,
            "system": systemPrompt,
            "messages": messages,
            "output_config": outputConfig,
        ]
        return try JSONSerialization.data(
            withJSONObject: body,
            options: [.sortedKeys]
        )
    }

    static func parsePost(
        _ kind: PostKind,
        data: Data,
        statusCode: Int
    ) throws -> GeneratedPost {
        guard (200..<300).contains(statusCode) else {
            throw PostGenerationError.http(
                status: statusCode,
                message: errorMessage(from: data)
            )
        }
        guard
            let root = try? JSONSerialization.jsonObject(with: data)
                as? [String: Any],
            let content = root["content"] as? [[String: Any]],
            let textBlock = content.first(where: {
                ($0["type"] as? String) == "text"
            }),
            let text = textBlock["text"] as? String,
            let jsonData = text.data(using: .utf8)
        else {
            throw PostGenerationError.malformedResponse(
                "missing text content block"
            )
        }

        switch kind {
        case .linkedIn:
            return GeneratedPost(
                kind: .linkedIn,
                linkedIn: try decodeLinkedIn(jsonData),
                instagram: nil
            )
        case .instagram:
            return GeneratedPost(
                kind: .instagram,
                linkedIn: nil,
                instagram: try decodeInstagram(jsonData)
            )
        }
    }

    private static func decodeLinkedIn(_ data: Data) throws -> LinkedInAngle {
        guard let angle = try? JSONDecoder().decode(
            LinkedInAngle.self,
            from: data
        ) else {
            throw PostGenerationError.malformedResponse(
                "LinkedIn JSON did not decode"
            )
        }
        guard angle.points.count == 3 else {
            throw PostGenerationError.malformedResponse(
                "expected exactly 3 points, got \(angle.points.count)"
            )
        }
        guard !angle.hook.trimmingCharacters(in: .whitespacesAndNewlines)
            .isEmpty
        else {
            throw PostGenerationError.malformedResponse("empty hook")
        }
        return angle
    }

    private static func decodeInstagram(
        _ data: Data
    ) throws -> InstagramCarousel {
        guard let carousel = try? JSONDecoder().decode(
            InstagramCarousel.self,
            from: data
        ) else {
            throw PostGenerationError.malformedResponse(
                "Instagram JSON did not decode"
            )
        }
        guard carousel.slides.count == 4 else {
            throw PostGenerationError.malformedResponse(
                "expected exactly 4 slides, got \(carousel.slides.count)"
            )
        }
        guard !carousel.cta.trimmingCharacters(in: .whitespacesAndNewlines)
            .isEmpty
        else {
            throw PostGenerationError.malformedResponse("empty CTA")
        }
        return carousel
    }

    private static func errorMessage(from data: Data) -> String {
        guard
            let root = try? JSONSerialization.jsonObject(with: data)
                as? [String: Any],
            let error = root["error"] as? [String: Any],
            let message = error["message"] as? String
        else {
            return "unknown error"
        }
        return message
    }

    private static func schema(for kind: PostKind) throws -> [String: Any] {
        let json: String
        switch kind {
        case .linkedIn: json = linkedInSchemaJSON
        case .instagram: json = instagramSchemaJSON
        }
        guard
            let data = json.data(using: .utf8),
            let dict = try JSONSerialization.jsonObject(with: data)
                as? [String: Any]
        else {
            throw PostGenerationError.malformedResponse("invalid schema")
        }
        return dict
    }

    // Mirror the constraints from the old Python BRIEF_SCHEMA: the array
    // lengths are validated locally after decoding, not in the JSON schema.
    private static let linkedInSchemaJSON = """
        {"type":"object","additionalProperties":false,\
        "properties":{"hook":{"type":"string"},\
        "points":{"type":"array","items":{"type":"string"},\
        "description":"Exactly three concise talking points."}},\
        "required":["hook","points"]}
        """

    private static let instagramSchemaJSON = """
        {"type":"object","additionalProperties":false,\
        "properties":{"slides":{"type":"array","items":{"type":"string"},\
        "description":"Exactly four slide texts."},\
        "cta":{"type":"string"}},"required":["slides","cta"]}
        """

    private static let systemPrompt = """
        You write factual, concise social posts from an AI news summary. Use \
        only the supplied material. Never invent facts, quotes, dates, \
        numbers, or implications. No full article text is available, so keep \
        every claim within the supplied summary.
        """

    private static func userPrompt(
        _ kind: PostKind,
        for item: DigestItem
    ) -> String {
        let ask: String
        switch kind {
        case .linkedIn:
            ask = "Write a LinkedIn post: one scroll-stopping hook line and "
                + "exactly three concise talking points."
        case .instagram:
            ask = "Write an Instagram carousel: exactly four short slide "
                + "texts and one call to action."
        }
        return """
            \(ask)

            Title: \(item.title)
            Source: \(item.source)
            URL: \(item.url.absoluteString)
            Category: \(item.category ?? "unclassified")

            What happened:
            \(item.whatHappened)

            Why it matters:
            \(item.whyItMatters)

            Caution:
            \(item.caution)

            No full article text is available. Stay within the summary above; \
            do not add facts, numbers, or quotes that are not present.
            """
    }
}
