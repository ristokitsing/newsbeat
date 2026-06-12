import Foundation

@MainActor
final class FeedPreferences: ObservableObject {
    enum SourceMode: String, CaseIterable, Identifiable {
        case local
        case remote

        var id: String { rawValue }
        var title: String {
            switch self {
            case .local: "Local file"
            case .remote: "Remote URL"
            }
        }
    }

    @Published var sourceMode: SourceMode {
        didSet { defaults.set(sourceMode.rawValue, forKey: Keys.sourceMode) }
    }

    @Published var localPath: String {
        didSet { defaults.set(localPath, forKey: Keys.localPath) }
    }

    @Published var remoteURL: String {
        didSet { defaults.set(remoteURL, forKey: Keys.remoteURL) }
    }

    /// Anthropic model used for on-demand post generation in the app.
    @Published var postModel: String {
        didSet { defaults.set(postModel, forKey: Keys.postModel) }
    }

    private let defaults: UserDefaults

    init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
        sourceMode = SourceMode(
            rawValue: defaults.string(forKey: Keys.sourceMode) ?? ""
        ) ?? Self.defaultSourceMode
        localPath = defaults.string(forKey: Keys.localPath) ?? Self.defaultLocalPath
        remoteURL = defaults.string(forKey: Keys.remoteURL) ?? ""
        postModel = defaults.string(forKey: Keys.postModel)
            ?? PostGenerationService.defaultModel
    }

    func selectLocalFile(_ url: URL) {
        localPath = url.path
        sourceMode = .local
        if let bookmark = try? url.bookmarkData() {
            defaults.set(bookmark, forKey: Keys.localBookmark)
        }
    }

    func selectedSource() throws -> FeedSource {
        switch sourceMode {
        case .local:
            if let data = defaults.data(forKey: Keys.localBookmark) {
                var stale = false
                if let url = try? URL(
                    resolvingBookmarkData: data,
                    bookmarkDataIsStale: &stale
                ) {
                    if stale {
                        selectLocalFile(url)
                    }
                    return .local(url)
                }
            }
            guard !localPath.trimmingCharacters(in: .whitespaces).isEmpty else {
                throw FeedError.invalidLocalPath
            }
            return .local(URL(fileURLWithPath: localPath))
        case .remote:
            guard let url = URL(string: remoteURL),
                  let scheme = url.scheme?.lowercased(),
                  ["http", "https"].contains(scheme)
            else {
                throw FeedError.invalidRemoteURL
            }
            return .remote(url)
        }
    }

    private enum Keys {
        static let sourceMode = "feed.sourceMode"
        static let localPath = "feed.localPath"
        static let localBookmark = "feed.localBookmark"
        static let remoteURL = "feed.remoteURL"
        static let postModel = "post.model"
    }

    private static var defaultSourceMode: SourceMode {
#if os(macOS)
        .local
#else
        .remote
#endif
    }

    private static var defaultLocalPath: String {
#if os(macOS)
        FileManager.default.homeDirectoryForCurrentUser
            .appending(path: "Projects/newsbeat/feed/digest.json").path
#else
        ""
#endif
    }
}

enum FeedSource: Sendable {
    case local(URL)
    case remote(URL)
}

enum FeedError: LocalizedError {
    case invalidLocalPath
    case invalidRemoteURL
    case noCachedFeed
    case unsupportedVersion(Int)

    var errorDescription: String? {
        switch self {
        case .invalidLocalPath:
            "Choose a local digest.json file."
        case .invalidRemoteURL:
            "Enter a valid HTTP or HTTPS digest URL."
        case .noCachedFeed:
            "No cached digest is available."
        case let .unsupportedVersion(version):
            "Feed version \(version) is not supported."
        }
    }
}

