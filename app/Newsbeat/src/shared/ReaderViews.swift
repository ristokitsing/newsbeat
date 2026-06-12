import SwiftUI
import UniformTypeIdentifiers

struct ReaderView: View {
    @EnvironmentObject private var store: DigestStore
    @EnvironmentObject private var preferences: FeedPreferences
    @State private var showingSettings = false

    var body: some View {
        NavigationSplitView {
            List(selection: $store.selectedItemID) {
                ForEach(store.groupedItems, id: \.date) { group in
                    Section(Self.sectionTitle(group.date)) {
                        ForEach(group.items) { item in
                            DigestRow(item: item)
                                .tag(item.id)
                        }
                    }
                }
            }
            .overlay {
                if !store.isLoading && store.groupedItems.isEmpty {
                    ContentUnavailableView(
                        "No stories",
                        systemImage: "newspaper",
                        description: Text(store.statusMessage)
                    )
                }
            }
            .navigationTitle("newsbeat")
            .toolbar {
                ToolbarItemGroup {
                    Button {
                        Task { await store.reload() }
                    } label: {
                        Label("Refresh", systemImage: "arrow.clockwise")
                    }
                    .disabled(store.isLoading)

                    Button {
                        showingSettings = true
                    } label: {
                        Label("Settings", systemImage: "gear")
                    }
                }
            }
            .safeAreaInset(edge: .bottom) {
                StatusBar(
                    message: store.statusMessage,
                    isLoading: store.isLoading,
                    isCached: store.isShowingCachedData
                )
            }
        } detail: {
            if let item = store.selectedItem {
                DigestDetailView(item: item)
            } else {
                ContentUnavailableView(
                    "Select a story",
                    systemImage: "doc.text.magnifyingglass"
                )
            }
        }
        .sheet(isPresented: $showingSettings) {
            SettingsView()
                .environmentObject(store)
                .environmentObject(preferences)
        }
    }

    private static func sectionTitle(_ date: String) -> String {
        guard let parsed = try? Date(date, strategy: .iso8601.year().month().day())
        else {
            return date
        }
        return parsed.formatted(date: .complete, time: .omitted)
    }
}

private struct DigestRow: View {
    let item: DigestItem

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(item.title)
                .font(.headline)
                .lineLimit(3)
            Text(item.whyItMatters)
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .lineLimit(2)
            HStack {
                Text(item.source)
                if let category = item.category {
                    Text(category.capitalized)
                        .padding(.horizontal, 6)
                        .padding(.vertical, 2)
                        .background(.secondary.opacity(0.12), in: Capsule())
                }
                Text(item.digestSlot.uppercased())
            }
            .font(.caption)
            .foregroundStyle(.secondary)
        }
        .padding(.vertical, 4)
    }
}

private struct StatusBar: View {
    let message: String
    let isLoading: Bool
    let isCached: Bool

    var body: some View {
        HStack(spacing: 8) {
            if isLoading {
                ProgressView()
                    .controlSize(.small)
            } else if isCached {
                Image(systemName: "externaldrive.badge.exclamationmark")
            }
            Text(message)
                .font(.caption)
                .foregroundStyle(.secondary)
                .lineLimit(2)
            Spacer()
        }
        .padding(10)
        .background(.bar)
    }
}

struct DigestDetailView: View {
    let item: DigestItem
    @State private var copiedMessage: String?

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                VStack(alignment: .leading, spacing: 10) {
                    Text(item.title)
                        .font(.largeTitle.bold())
                        .textSelection(.enabled)
                    HStack {
                        Label(item.source, systemImage: "building.2")
                        if let score = item.score {
                            Label(score.formatted(.number.precision(.fractionLength(1))), systemImage: "star")
                        }
                    }
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                }

                DetailSection(title: "What happened", text: item.whatHappened)
                DetailSection(title: "Why it matters", text: item.whyItMatters)

                DraftSection(
                    title: "LinkedIn angle",
                    text: item.linkedInText,
                    copyLabel: "Copy LinkedIn"
                ) {
                    copy(item.linkedInText, message: "LinkedIn draft copied")
                }

                DraftSection(
                    title: "Instagram carousel",
                    text: item.instagramText,
                    copyLabel: "Copy Instagram"
                ) {
                    copy(item.instagramText, message: "Instagram draft copied")
                }

                DetailSection(title: "Caution", text: item.caution)

                HStack {
                    Link(destination: item.url) {
                        Label("Open source article", systemImage: "safari")
                    }
                    .buttonStyle(.borderedProminent)

#if os(iOS)
                    ShareLink(
                        item: item.linkedInText,
                        subject: Text(item.title)
                    ) {
                        Label("Share LinkedIn", systemImage: "square.and.arrow.up")
                    }
                    .buttonStyle(.bordered)

                    ShareLink(
                        item: item.instagramText,
                        subject: Text(item.title)
                    ) {
                        Label("Share Instagram", systemImage: "square.and.arrow.up")
                    }
                    .buttonStyle(.bordered)
#endif
                }

                if let copiedMessage {
                    Label(copiedMessage, systemImage: "checkmark.circle.fill")
                        .foregroundStyle(.green)
                        .transition(.opacity)
                }
            }
            .frame(maxWidth: 760, alignment: .leading)
            .padding(24)
        }
        .navigationTitle(item.title)
    }

    private func copy(_ text: String, message: String) {
        PlatformActions.copy(text)
        withAnimation {
            copiedMessage = message
        }
        Task {
            try? await Task.sleep(for: .seconds(2))
            withAnimation {
                copiedMessage = nil
            }
        }
    }
}

private struct DetailSection: View {
    let title: String
    let text: String

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title)
                .font(.title2.bold())
            Text(text)
                .textSelection(.enabled)
        }
    }
}

private struct DraftSection: View {
    let title: String
    let text: String
    let copyLabel: String
    let copyAction: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text(title)
                    .font(.title2.bold())
                Spacer()
                Button(copyLabel, systemImage: "doc.on.doc", action: copyAction)
                    .buttonStyle(.bordered)
            }
            Text(text)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding()
                .background(.secondary.opacity(0.1), in: RoundedRectangle(cornerRadius: 12))
                .textSelection(.enabled)
        }
    }
}

struct SettingsView: View {
    @Environment(\.dismiss) private var dismiss
    @EnvironmentObject private var store: DigestStore
    @EnvironmentObject private var preferences: FeedPreferences
    @State private var choosingFile = false

    var body: some View {
        NavigationStack {
            Form {
                Section("Feed source") {
                    Picker("Source", selection: $preferences.sourceMode) {
                        ForEach(FeedPreferences.SourceMode.allCases) { mode in
                            Text(mode.title).tag(mode)
                        }
                    }
                    .pickerStyle(.segmented)

                    if preferences.sourceMode == .local {
                        TextField("Path to digest.json", text: $preferences.localPath)
                            .textFieldStyle(.roundedBorder)
                        Button("Choose digest.json", systemImage: "folder") {
                            choosingFile = true
                        }
                    } else {
                        TextField(
                            "https://example.com/feed/digest.json",
                            text: $preferences.remoteURL
                        )
                        .textFieldStyle(.roundedBorder)
#if os(iOS)
                        .textInputAutocapitalization(.never)
                        .keyboardType(.URL)
#endif
                    }
                }

#if os(macOS)
                MacHostSettingsSection()
#endif
            }
            .formStyle(.grouped)
            .navigationTitle("Settings")
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") {
                        Task { await store.reload() }
                        dismiss()
                    }
                }
            }
        }
#if os(macOS)
        .frame(minWidth: 500, minHeight: 420)
#endif
        .fileImporter(
            isPresented: $choosingFile,
            allowedContentTypes: [.json],
            allowsMultipleSelection: false
        ) { result in
            guard case let .success(urls) = result, let url = urls.first else {
                return
            }
            preferences.selectLocalFile(url)
        }
    }
}
