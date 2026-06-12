import Foundation

@MainActor
final class DigestStore: ObservableObject {
    @Published private(set) var feed: DigestFeed?
    @Published private(set) var isLoading = false
    @Published private(set) var statusMessage = "Loading digest…"
    @Published private(set) var isShowingCachedData = false
    @Published var selectedItemID: DigestItem.ID?

    let preferences: FeedPreferences
    private let service: DigestService

    init(
        preferences: FeedPreferences,
        service: DigestService = DigestService()
    ) {
        self.preferences = preferences
        self.service = service
    }

    var groupedItems: [(date: String, items: [DigestItem])] {
        let grouped = Dictionary(grouping: feed?.items ?? [], by: \.digestDate)
        return grouped.keys.sorted(by: >).map {
            ($0, grouped[$0, default: []])
        }
    }

    var selectedItem: DigestItem? {
        guard let selectedItemID else { return nil }
        return feed?.items.first { $0.id == selectedItemID }
    }

    var todayCount: Int {
        let today = Date.now.formatted(.iso8601.year().month().day())
        return feed?.items.count { $0.digestDate == today } ?? 0
    }

    func bootstrap() async {
        await reload()
    }

    func reload() async {
        guard !isLoading else { return }
        isLoading = true
        defer { isLoading = false }

        do {
            let source = try preferences.selectedSource()
            let loaded = try await service.load(source: source)
            apply(loaded)
            isShowingCachedData = false
            statusMessage = loaded.items.isEmpty
                ? "The latest digest contains no selected stories."
                : "Updated \(Self.relativeTimestamp(loaded.generatedDate))"
        } catch {
            do {
                let cached = try await service.loadCache()
                apply(cached)
                isShowingCachedData = true
                statusMessage = "Offline cache · \(error.localizedDescription)"
            } catch {
                feed = nil
                statusMessage = error.localizedDescription
            }
        }
    }

    private func apply(_ loaded: DigestFeed) {
        feed = loaded
        if let selectedItemID,
           !loaded.items.contains(where: { $0.id == selectedItemID }) {
            self.selectedItemID = nil
        }
    }

    private static func relativeTimestamp(_ date: Date?) -> String {
        guard let date else { return "recently" }
        return date.formatted(date: .abbreviated, time: .shortened)
    }
}

