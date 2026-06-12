import XCTest
@testable import NewsbeatMac

final class FeedModelsTests: XCTestCase {
    func testDecodesPublishedFeedAndFormatsDrafts() throws {
        let data = Data(
            """
            {
              "version": 1,
              "generated_at": "2026-06-10T19:05:43.870629+00:00",
              "timezone": "Europe/Tallinn",
              "items": [{
                "id": 1,
                "title": "A useful AI release",
                "url": "https://example.com/story",
                "canonical_url": "https://example.com/story",
                "source": "Example",
                "published_at": null,
                "digest_date": "2026-06-10",
                "digest_slot": "pm",
                "category": "models",
                "score": 8.5,
                "what_happened": "A model shipped.",
                "why_it_matters": "It changes a workflow.",
                "linkedin_angle": {
                  "hook": "Start here.",
                  "points": ["One", "Two", "Three"]
                },
                "instagram_carousel": {
                  "slides": ["A", "B", "C", "D"],
                  "cta": "Try it."
                },
                "caution": "Independent testing is limited."
              }]
            }
            """.utf8
        )

        let feed = try JSONDecoder().decode(DigestFeed.self, from: data)

        XCTAssertEqual(feed.items.count, 1)
        XCTAssertTrue(feed.items[0].linkedInText.contains("• One"))
        XCTAssertTrue(feed.items[0].instagramText.contains("Slide 4"))
        XCTAssertTrue(
            feed.items[0].linkedInText.contains(
                "Source: https://example.com/story"
            )
        )
        XCTAssertTrue(
            feed.items[0].instagramText.contains(
                "Source: https://example.com/story"
            )
        )
        XCTAssertNotNil(feed.generatedDate)
    }

    func testLoadsLocalFeedAndRetainsOfflineCache() async throws {
        let directory = FileManager.default.temporaryDirectory
            .appending(path: UUID().uuidString, directoryHint: .isDirectory)
        try FileManager.default.createDirectory(
            at: directory,
            withIntermediateDirectories: true
        )
        defer { try? FileManager.default.removeItem(at: directory) }

        let sourceURL = directory.appending(path: "digest.json")
        let cacheURL = directory.appending(path: "cache/digest.json")
        try """
        {
          "version": 1,
          "generated_at": "2026-06-10T19:05:43+00:00",
          "timezone": "Europe/Tallinn",
          "items": []
        }
        """.write(to: sourceURL, atomically: true, encoding: .utf8)

        let service = DigestService(cacheURL: cacheURL)
        let local = try await service.load(source: .local(sourceURL))
        try FileManager.default.removeItem(at: sourceURL)
        let cached = try await service.loadCache()

        XCTAssertEqual(local.generatedAt, cached.generatedAt)
        XCTAssertTrue(cached.items.isEmpty)
    }

    @MainActor
    func testMacHostLaunchesConfiguredChildProcess() async throws {
        let suiteName = "NewsbeatMacTests.\(UUID().uuidString)"
        let defaults = try XCTUnwrap(UserDefaults(suiteName: suiteName))
        defer { defaults.removePersistentDomain(forName: suiteName) }

        let directory = FileManager.default.temporaryDirectory
            .appending(path: UUID().uuidString, directoryHint: .isDirectory)
        try FileManager.default.createDirectory(
            at: directory,
            withIntermediateDirectories: true
        )
        defer { try? FileManager.default.removeItem(at: directory) }

        let preferences = FeedPreferences(defaults: defaults)
        let coordinator = MacHostCoordinator(
            preferences: preferences,
            defaults: defaults
        )
        coordinator.repositoryPath = directory.path
        coordinator.pythonPath = "/bin/echo"

        coordinator.runNow()
        while coordinator.isRunning {
            try await Task.sleep(for: .milliseconds(50))
        }

        XCTAssertEqual(
            coordinator.statusMessage,
            "newsbeat-digest completed successfully."
        )
        XCTAssertTrue(coordinator.lastOutput.contains("newsbeat_digest run"))
    }
}
