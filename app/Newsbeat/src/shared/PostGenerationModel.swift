import Foundation

/// Main-actor bridge between the `PostGenerationService`/`GeneratedPostStore`
/// actors and SwiftUI. Publishes the cached posts so detail views update when a
/// draft is generated or regenerated.
@MainActor
final class PostGenerationModel: ObservableObject {
    @Published private(set) var posts: [String: GeneratedPost] = [:]

    private let service: PostGenerationService
    private let store: GeneratedPostStore

    init(
        service: PostGenerationService = PostGenerationService(),
        store: GeneratedPostStore = GeneratedPostStore()
    ) {
        self.service = service
        self.store = store
    }

    func loadCache() async {
        posts = await store.all()
    }

    func post(for item: DigestItem, kind: PostKind) -> GeneratedPost? {
        posts[GeneratedPostStore.key(itemID: item.id, kind: kind)]
    }

    func generate(
        _ kind: PostKind,
        for item: DigestItem,
        apiKey: String,
        model: String
    ) async throws {
        let post = try await service.generate(
            kind,
            for: item,
            apiKey: apiKey,
            model: model
        )
        await store.save(post, for: item.id, kind: kind)
        posts[GeneratedPostStore.key(itemID: item.id, kind: kind)] = post
    }
}
