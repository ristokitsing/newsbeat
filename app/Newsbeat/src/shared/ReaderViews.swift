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
                DigestDetailView(item: item) { showingSettings = true }
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
    let openSettings: () -> Void
    @State private var copiedMessage: String?

    init(item: DigestItem, openSettings: @escaping () -> Void) {
        self.item = item
        self.openSettings = openSettings
    }

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

                PostSection(kind: .linkedIn, item: item, openSettings: openSettings, onCopy: copy)
                PostSection(kind: .instagram, item: item, openSettings: openSettings, onCopy: copy)

                DetailSection(title: "Caution", text: item.caution)

                Link(destination: item.url) {
                    Label("Open source article", systemImage: "safari")
                }
                .buttonStyle(.borderedProminent)

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

/// A LinkedIn or Instagram draft section. Shows a pre-generated legacy draft, a
/// cached on-demand draft (with Regenerate), or a Create button that calls
/// Claude. Surfaces loading, error, and missing-API-key states.
private struct PostSection: View {
    let kind: PostKind
    let item: DigestItem
    let openSettings: () -> Void
    let onCopy: (String, String) -> Void

    @EnvironmentObject private var posts: PostGenerationModel
    @EnvironmentObject private var preferences: FeedPreferences
    @State private var phase: Phase = .idle

    enum Phase: Equatable {
        case idle
        case loading
        case error(String)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(kind.title)
                .font(.title2.bold())
            content
        }
    }

    @ViewBuilder private var content: some View {
        if let preGenerated = preGeneratedText {
            draft(text: preGenerated, canRegenerate: false)
        } else if let generated = posts.post(for: item, kind: kind) {
            draft(text: generated.text(url: item.url), canRegenerate: true)
        } else {
            switch phase {
            case .loading:
                HStack(spacing: 8) {
                    ProgressView().controlSize(.small)
                    Text("Generating \(kind.shortName) post…")
                        .foregroundStyle(.secondary)
                }
            case let .error(message):
                VStack(alignment: .leading, spacing: 8) {
                    Label(message, systemImage: "exclamationmark.triangle")
                        .foregroundStyle(.orange)
                    Button("Retry", systemImage: "arrow.clockwise") { generate() }
                        .buttonStyle(.bordered)
                }
            case .idle:
                if hasAPIKey {
                    Button("Create \(kind.shortName) post", systemImage: "sparkles") {
                        generate()
                    }
                    .buttonStyle(.borderedProminent)
                } else {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Add your Anthropic API key in Settings to generate a \(kind.shortName) post.")
                            .foregroundStyle(.secondary)
                        Button("Open Settings", systemImage: "gear") { openSettings() }
                            .buttonStyle(.bordered)
                    }
                }
            }
        }
    }

    private var preGeneratedText: String? {
        kind == .linkedIn ? item.linkedInText : item.instagramText
    }

    private var hasAPIKey: Bool {
        !KeychainStore.readAPIKey()
            .trimmingCharacters(in: .whitespacesAndNewlines)
            .isEmpty
    }

    @ViewBuilder private func draft(text: String, canRegenerate: Bool) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(text)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding()
                .background(.secondary.opacity(0.1), in: RoundedRectangle(cornerRadius: 12))
                .textSelection(.enabled)
            HStack {
                Button("Copy \(kind.shortName)", systemImage: "doc.on.doc") {
                    onCopy(text, "\(kind.shortName) draft copied")
                }
                .buttonStyle(.bordered)

                if canRegenerate {
                    if phase == .loading {
                        ProgressView().controlSize(.small)
                    } else {
                        Button("Regenerate", systemImage: "arrow.clockwise") { generate() }
                            .buttonStyle(.bordered)
                    }
                }

#if os(iOS)
                ShareLink(item: text, subject: Text(item.title)) {
                    Label("Share", systemImage: "square.and.arrow.up")
                }
                .buttonStyle(.bordered)
#endif
            }
            if case let .error(message) = phase {
                Label(message, systemImage: "exclamationmark.triangle")
                    .font(.caption)
                    .foregroundStyle(.orange)
            }
        }
    }

    private func generate() {
        phase = .loading
        let apiKey = KeychainStore.readAPIKey()
        let model = preferences.postModel
        Task {
            do {
                try await posts.generate(kind, for: item, apiKey: apiKey, model: model)
                phase = .idle
            } catch {
                phase = .error(error.localizedDescription)
            }
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

                PostGenerationSettingsSection()

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

/// Shared on both platforms: stores the Anthropic API key in the Keychain (the
/// same entry the macOS host coordinator reuses) and the post-generation model
/// in preferences.
struct PostGenerationSettingsSection: View {
    @EnvironmentObject private var preferences: FeedPreferences
    @State private var apiKeyDraft = ""
    @State private var savedMessage: String?

    var body: some View {
        Section("Post generation") {
            SecureField("Anthropic API key", text: $apiKeyDraft)
                .textFieldStyle(.roundedBorder)
#if os(iOS)
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled()
#endif
            TextField("Model", text: $preferences.postModel)
                .textFieldStyle(.roundedBorder)
#if os(iOS)
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled()
#endif

            Button("Save API key to Keychain") { saveKey() }

            if let savedMessage {
                Text(savedMessage)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            Text("The key is stored in this device's Keychain and used for on-demand LinkedIn and Instagram drafts. On macOS, the local newsbeat-digest host reuses the same Keychain entry.")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .onAppear { apiKeyDraft = KeychainStore.readAPIKey() }
    }

    private func saveKey() {
        let trimmed = apiKeyDraft.trimmingCharacters(in: .whitespacesAndNewlines)
        do {
            try KeychainStore.saveAPIKey(trimmed)
            savedMessage = trimmed.isEmpty
                ? "API key removed."
                : "API key saved to Keychain."
        } catch {
            savedMessage = error.localizedDescription
        }
    }
}
