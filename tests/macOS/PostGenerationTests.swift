import XCTest
@testable import NewsbeatMac

final class PostGenerationTests: XCTestCase {
    private func makeItem() throws -> DigestItem {
        let data = Data(
            """
            {
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
              "caution": "Independent testing is limited."
            }
            """.utf8
        )
        return try JSONDecoder().decode(DigestItem.self, from: data)
    }

    func testRequestBodyContainsModelSchemaAndSystem() throws {
        let item = try makeItem()
        let body = try PostGenerationService.requestBody(
            .linkedIn,
            for: item,
            model: "claude-haiku-4-5"
        )
        let root = try XCTUnwrap(
            JSONSerialization.jsonObject(with: body) as? [String: Any]
        )

        XCTAssertEqual(root["model"] as? String, "claude-haiku-4-5")
        let system = try XCTUnwrap(root["system"] as? String)
        XCTAssertFalse(system.isEmpty)

        let outputConfig = try XCTUnwrap(root["output_config"] as? [String: Any])
        let format = try XCTUnwrap(outputConfig["format"] as? [String: Any])
        XCTAssertEqual(format["type"] as? String, "json_schema")
        let schema = try XCTUnwrap(format["schema"] as? [String: Any])
        let properties = try XCTUnwrap(schema["properties"] as? [String: Any])
        XCTAssertNotNil(properties["hook"])
        XCTAssertNotNil(properties["points"])

        let messages = try XCTUnwrap(root["messages"] as? [[String: String]])
        XCTAssertTrue(
            messages.first?["content"]?.contains("A useful AI release") == true
        )
    }

    func testInstagramSchemaUsesSlidesAndCta() throws {
        let item = try makeItem()
        let body = try PostGenerationService.requestBody(
            .instagram,
            for: item,
            model: "claude-haiku-4-5"
        )
        let root = try XCTUnwrap(
            JSONSerialization.jsonObject(with: body) as? [String: Any]
        )
        let outputConfig = try XCTUnwrap(root["output_config"] as? [String: Any])
        let format = try XCTUnwrap(outputConfig["format"] as? [String: Any])
        let schema = try XCTUnwrap(format["schema"] as? [String: Any])
        let properties = try XCTUnwrap(schema["properties"] as? [String: Any])
        XCTAssertNotNil(properties["slides"])
        XCTAssertNotNil(properties["cta"])
    }

    func testParsesValidLinkedInResponse() throws {
        let item = try makeItem()
        let data = cannedResponse(
            text: #"{"hook":"Start here.","points":["One","Two","Three"]}"#
        )
        let post = try PostGenerationService.parsePost(
            .linkedIn,
            data: data,
            statusCode: 200
        )
        XCTAssertEqual(post.kind, .linkedIn)
        XCTAssertEqual(post.linkedIn?.points.count, 3)
        let text = post.text(url: item.url)
        XCTAssertTrue(text.contains("Start here."))
        XCTAssertTrue(text.contains("• One"))
        XCTAssertTrue(text.contains("Source: https://example.com/story"))
    }

    func testParsesValidInstagramResponse() throws {
        let item = try makeItem()
        let data = cannedResponse(
            text: #"{"slides":["A","B","C","D"],"cta":"Try it."}"#
        )
        let post = try PostGenerationService.parsePost(
            .instagram,
            data: data,
            statusCode: 200
        )
        XCTAssertEqual(post.instagram?.slides.count, 4)
        let text = post.text(url: item.url)
        XCTAssertTrue(text.contains("Slide 4"))
        XCTAssertTrue(text.contains("Try it."))
    }

    func testRejectsWrongPointCount() {
        let data = cannedResponse(
            text: #"{"hook":"Start here.","points":["One","Two"]}"#
        )
        XCTAssertThrowsError(
            try PostGenerationService.parsePost(
                .linkedIn,
                data: data,
                statusCode: 200
            )
        )
    }

    func testRejectsNonJSONText() {
        let data = cannedResponse(text: "not json at all")
        XCTAssertThrowsError(
            try PostGenerationService.parsePost(
                .linkedIn,
                data: data,
                statusCode: 200
            )
        )
    }

    func testHTTPErrorSurfacesAnthropicMessage() {
        let data = Data(
            #"{"type":"error","error":{"type":"authentication_error","message":"invalid x-api-key"}}"#
                .utf8
        )
        XCTAssertThrowsError(
            try PostGenerationService.parsePost(
                .linkedIn,
                data: data,
                statusCode: 401
            )
        ) { error in
            guard case let PostGenerationError.http(status, message) = error else {
                return XCTFail("expected http error, got \(error)")
            }
            XCTAssertEqual(status, 401)
            XCTAssertTrue(message.contains("invalid x-api-key"))
        }
    }

    private func cannedResponse(text: String) -> Data {
        let payload: [String: Any] = [
            "content": [
                ["type": "text", "text": text],
            ],
        ]
        return try! JSONSerialization.data(withJSONObject: payload)
    }
}
