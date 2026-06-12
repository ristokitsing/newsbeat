import Foundation

struct DigestFeed: Codable, Sendable {
    let version: Int
    let generatedAt: String
    let timezone: String
    let items: [DigestItem]

    enum CodingKeys: String, CodingKey {
        case version
        case generatedAt = "generated_at"
        case timezone
        case items
    }

    var generatedDate: Date? {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let date = formatter.date(from: generatedAt) {
            return date
        }
        formatter.formatOptions = [.withInternetDateTime]
        return formatter.date(from: generatedAt)
    }
}

struct DigestItem: Codable, Identifiable, Hashable, Sendable {
    let id: Int
    let title: String
    let url: URL
    let canonicalURL: URL?
    let source: String
    let publishedAt: String?
    let digestDate: String
    let digestSlot: String
    let category: String?
    let score: Double?
    let whatHappened: String
    let whyItMatters: String
    let linkedinAngle: LinkedInAngle
    let instagramCarousel: InstagramCarousel
    let caution: String

    enum CodingKeys: String, CodingKey {
        case id
        case title
        case url
        case canonicalURL = "canonical_url"
        case source
        case publishedAt = "published_at"
        case digestDate = "digest_date"
        case digestSlot = "digest_slot"
        case category
        case score
        case whatHappened = "what_happened"
        case whyItMatters = "why_it_matters"
        case linkedinAngle = "linkedin_angle"
        case instagramCarousel = "instagram_carousel"
        case caution
    }

    var linkedInText: String {
        (
            [linkedinAngle.hook]
            + linkedinAngle.points.map { "• \($0)" }
            + ["Source: \(url.absoluteString)"]
        )
            .joined(separator: "\n\n")
    }

    var instagramText: String {
        let slides = instagramCarousel.slides.enumerated().map {
            "Slide \($0.offset + 1)\n\($0.element)"
        }
        return (
            slides
            + [
                "CTA\n\(instagramCarousel.cta)",
                "Source: \(url.absoluteString)",
            ]
        )
            .joined(separator: "\n\n")
    }
}

struct LinkedInAngle: Codable, Hashable, Sendable {
    let hook: String
    let points: [String]
}

struct InstagramCarousel: Codable, Hashable, Sendable {
    let slides: [String]
    let cta: String
}
