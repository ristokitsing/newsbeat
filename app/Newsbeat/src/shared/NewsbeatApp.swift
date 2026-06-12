import SwiftUI
#if os(macOS)
import AppKit
#endif

@main
struct NewsbeatApp: App {
    @StateObject private var preferences: FeedPreferences
    @StateObject private var store: DigestStore
#if os(macOS)
    @StateObject private var hostCoordinator: MacHostCoordinator
#endif

    init() {
        let preferences = FeedPreferences()
        _preferences = StateObject(wrappedValue: preferences)
        _store = StateObject(
            wrappedValue: DigestStore(preferences: preferences)
        )
#if os(macOS)
        _hostCoordinator = StateObject(
            wrappedValue: MacHostCoordinator(preferences: preferences)
        )
#endif
    }

#if os(macOS)
    var body: some Scene {
        WindowGroup(id: "reader") {
            readerContent
                .environmentObject(hostCoordinator)
                .task {
                    await store.bootstrap()
                    hostCoordinator.start(store: store)
                }
                .onReceive(
                    NotificationCenter.default.publisher(
                        for: NSApplication.willTerminateNotification
                    )
                ) { _ in
                    hostCoordinator.stop()
                }
        }
        .defaultSize(width: 1100, height: 720)

        MenuBarExtra {
            MenuBarDigestView()
                .environmentObject(store)
                .environmentObject(hostCoordinator)
        } label: {
            Label(
                "\(store.todayCount)",
                systemImage: "newspaper"
            )
        }
    }
#else
    var body: some Scene {
        WindowGroup(id: "reader") {
            readerContent
                .task {
                    await store.bootstrap()
                }
        }
    }
#endif

    private var readerContent: some View {
        ReaderView()
            .environmentObject(preferences)
            .environmentObject(store)
    }
}
