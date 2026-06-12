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
    // The pipeline now publishes summary-only briefs; social drafts are
    // generated on demand in the app. Legacy feeds inside the 7-day window
    // still carry these, so they decode when present and stay nil otherwise.
    let linkedinAngle: LinkedInAngle?
    let instagramCarousel: InstagramCarousel?
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

    /// Formatted LinkedIn draft from the pre-generated angle, or nil when the
    /// brief is summary-only (the app generates it on demand instead).
    var linkedInText: String? {
        guard let linkedinAngle else { return nil }
        return formatLinkedIn(
            hook: linkedinAngle.hook,
            points: linkedinAngle.points,
            url: url
        )
    }

    /// Formatted Instagram draft from the pre-generated carousel, or nil when
    /// the brief is summary-only.
    var instagramText: String? {
        guard let instagramCarousel else { return nil }
        return formatInstagram(
            slides: instagramCarousel.slides,
            cta: instagramCarousel.cta,
            url: url
        )
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

/// Shared LinkedIn formatting used by both pre-generated and on-demand drafts.
func formatLinkedIn(hook: String, points: [String], url: URL) -> String {
    (
        [hook]
        + points.map { "• \($0)" }
        + ["Source: \(url.absoluteString)"]
    )
        .joined(separator: "\n\n")
}

/// Shared Instagram formatting used by both pre-generated and on-demand drafts.
func formatInstagram(slides: [String], cta: String, url: URL) -> String {
    let slideBlocks = slides.enumerated().map {
        "Slide \($0.offset + 1)\n\($0.element)"
    }
    return (
        slideBlocks
        + [
            "CTA\n\(cta)",
            "Source: \(url.absoluteString)",
        ]
    )
        .joined(separator: "\n\n")
}
