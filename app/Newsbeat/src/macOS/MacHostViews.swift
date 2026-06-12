import AppKit
import SwiftUI

struct MacHostSettingsSection: View {
    @EnvironmentObject private var host: MacHostCoordinator

    var body: some View {
        Section("Local newsbeat-digest host") {
            Toggle("Run newsbeat-digest while this app is open", isOn: $host.isEnabled)

            TextField("Repository path", text: $host.repositoryPath)
                .textFieldStyle(.roundedBorder)
            TextField("Python executable", text: $host.pythonPath)
                .textFieldStyle(.roundedBorder)

            SecureField("Anthropic API key (optional)", text: $host.apiKeyDraft)
                .textFieldStyle(.roundedBorder)

            HStack {
                Button("Save API key to Keychain") {
                    host.saveAPIKey()
                }
                Button("Run now") {
                    host.runNow()
                }
                .disabled(host.isRunning)
            }

            LabeledContent("Status", value: host.statusMessage)
            if !host.lastOutput.isEmpty {
                DisclosureGroup("Last CLI output") {
                    ScrollView {
                        Text(host.lastOutput)
                            .font(.system(.caption, design: .monospaced))
                            .textSelection(.enabled)
                            .frame(maxWidth: .infinity, alignment: .leading)
                    }
                    .frame(maxHeight: 140)
                }
            }

            Text(
                "Host mode checks at 08:00 and 17:00 local time and stops scheduling when the app exits. This personal macOS target intentionally runs without App Sandbox so it can launch the configured Python process."
            )
            .font(.caption)
            .foregroundStyle(.secondary)
        }
    }
}

struct MenuBarDigestView: View {
    @Environment(\.openWindow) private var openWindow
    @EnvironmentObject private var store: DigestStore
    @EnvironmentObject private var host: MacHostCoordinator

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("\(store.todayCount) stories today")
                .font(.headline)
            Text(host.statusMessage)
                .font(.caption)
                .foregroundStyle(.secondary)
                .lineLimit(3)

            ForEach(Array((store.feed?.items ?? []).prefix(3))) { item in
                Text(item.title)
                    .font(.caption)
                    .lineLimit(2)
            }

            Divider()

            Button("Open newsbeat") {
                openWindow(id: "reader")
                NSApp.activate(ignoringOtherApps: true)
            }
            Button("Refresh feed") {
                Task { await store.reload() }
            }
            Button("Run newsbeat-digest now") {
                host.runNow()
            }
            .disabled(host.isRunning)

            Divider()

            Button("Quit") {
                host.stop()
                NSApp.terminate(nil)
            }
        }
        .padding(12)
        .frame(width: 280)
    }
}
