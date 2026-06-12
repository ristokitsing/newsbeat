import Foundation

actor DigestService {
    private let cacheURL: URL

    init(cacheURL: URL? = nil) {
        self.cacheURL = cacheURL ?? Self.defaultCacheURL()
    }

    func load(source: FeedSource) async throws -> DigestFeed {
        let data: Data
        switch source {
        case let .local(url):
            let accessed = url.startAccessingSecurityScopedResource()
            defer {
                if accessed {
                    url.stopAccessingSecurityScopedResource()
                }
            }
            data = try Data(contentsOf: url)
        case let .remote(url):
            var request = URLRequest(url: url)
            request.timeoutInterval = 15
            request.cachePolicy = .reloadIgnoringLocalCacheData
            let (responseData, response) = try await URLSession.shared.data(for: request)
            guard let httpResponse = response as? HTTPURLResponse,
                  (200..<300).contains(httpResponse.statusCode)
            else {
                throw URLError(.badServerResponse)
            }
            data = responseData
        }

        let feed = try decode(data)
        try persistCache(data)
        return feed
    }

    func loadCache() throws -> DigestFeed {
        guard FileManager.default.fileExists(atPath: cacheURL.path) else {
            throw FeedError.noCachedFeed
        }
        return try decode(Data(contentsOf: cacheURL))
    }

    private func decode(_ data: Data) throws -> DigestFeed {
        let feed = try JSONDecoder().decode(DigestFeed.self, from: data)
        guard feed.version == 1 else {
            throw FeedError.unsupportedVersion(feed.version)
        }
        return feed
    }

    private func persistCache(_ data: Data) throws {
        let directory = cacheURL.deletingLastPathComponent()
        try FileManager.default.createDirectory(
            at: directory,
            withIntermediateDirectories: true
        )
        try data.write(to: cacheURL, options: .atomic)
    }

    private static func defaultCacheURL() -> URL {
        let base = FileManager.default.urls(
            for: .applicationSupportDirectory,
            in: .userDomainMask
        ).first ?? FileManager.default.temporaryDirectory
        return base
            .appending(path: "newsbeat", directoryHint: .isDirectory)
            .appending(path: "digest-cache.json")
    }
}
