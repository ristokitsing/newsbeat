import Foundation

/// Persists on-demand generated posts to Application Support so drafts survive
/// relaunch. Keyed by "<item id>-<kind>"; Regenerate overwrites.
actor GeneratedPostStore {
    private let cacheURL: URL
    private var posts: [String: GeneratedPost]

    init(cacheURL: URL? = nil) {
        let url = cacheURL ?? Self.defaultCacheURL()
        self.cacheURL = url
        self.posts = Self.load(from: url)
    }

    static func key(itemID: Int, kind: PostKind) -> String {
        "\(itemID)-\(kind.rawValue)"
    }

    func all() -> [String: GeneratedPost] {
        posts
    }

    func post(for itemID: Int, kind: PostKind) -> GeneratedPost? {
        posts[Self.key(itemID: itemID, kind: kind)]
    }

    func save(_ post: GeneratedPost, for itemID: Int, kind: PostKind) {
        posts[Self.key(itemID: itemID, kind: kind)] = post
        persist()
    }

    private func persist() {
        guard let data = try? JSONEncoder().encode(posts) else { return }
        let directory = cacheURL.deletingLastPathComponent()
        try? FileManager.default.createDirectory(
            at: directory,
            withIntermediateDirectories: true
        )
        try? data.write(to: cacheURL, options: .atomic)
    }

    private static func load(from url: URL) -> [String: GeneratedPost] {
        guard
            let data = try? Data(contentsOf: url),
            let decoded = try? JSONDecoder().decode(
                [String: GeneratedPost].self,
                from: data
            )
        else {
            return [:]
        }
        return decoded
    }

    private static func defaultCacheURL() -> URL {
        let base = FileManager.default.urls(
            for: .applicationSupportDirectory,
            in: .userDomainMask
        ).first ?? FileManager.default.temporaryDirectory
        return base
            .appending(path: "newsbeat", directoryHint: .isDirectory)
            .appending(path: "posts-cache.json")
    }
}
