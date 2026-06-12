import AppKit
import Foundation

@MainActor
final class MacHostCoordinator: ObservableObject {
    @Published var isEnabled: Bool {
        didSet {
            defaults.set(isEnabled, forKey: Keys.enabled)
            if isEnabled {
                beginSchedule()
                checkLaunchStaleness()
            } else {
                scheduleTimer?.invalidate()
                scheduleTimer = nil
            }
        }
    }

    @Published var repositoryPath: String {
        didSet { defaults.set(repositoryPath, forKey: Keys.repositoryPath) }
    }

    @Published var pythonPath: String {
        didSet { defaults.set(pythonPath, forKey: Keys.pythonPath) }
    }

    @Published private(set) var isRunning = false
    @Published private(set) var statusMessage = "Local host is disabled."
    @Published private(set) var lastOutput = ""

    private let defaults: UserDefaults
    private let preferences: FeedPreferences
    private weak var store: DigestStore?
    private var scheduleTimer: Timer?
    private var process: Process?
    private var hasStarted = false

    init(
        preferences: FeedPreferences,
        defaults: UserDefaults = .standard
    ) {
        self.preferences = preferences
        self.defaults = defaults

        let defaultRepository = FileManager.default.homeDirectoryForCurrentUser
            .appending(path: "Projects/newsbeat").path
        let storedRepository = defaults.string(forKey: Keys.repositoryPath)
            ?? defaultRepository
        repositoryPath = storedRepository
        pythonPath = defaults.string(forKey: Keys.pythonPath)
            ?? URL(fileURLWithPath: storedRepository)
                .appending(path: ".venv/bin/python").path
        isEnabled = defaults.bool(forKey: Keys.enabled)
    }

    func start(store: DigestStore) {
        self.store = store
        guard !hasStarted else { return }
        hasStarted = true

        if isEnabled {
            statusMessage = "Watching the 07:00, 11:00, 16:00, and 21:00 local schedule."
            beginSchedule()
            checkLaunchStaleness()
        }
    }

    func stop() {
        scheduleTimer?.invalidate()
        scheduleTimer = nil
        if process?.isRunning == true {
            process?.terminate()
        }
    }

    func runNow() {
        runPipeline(trigger: "Manual run")
    }

    private func beginSchedule() {
        guard scheduleTimer == nil else { return }
        scheduleTimer = Timer.scheduledTimer(
            withTimeInterval: 60,
            repeats: true
        ) { [weak self] _ in
            Task { @MainActor in
                self?.checkScheduledRun()
            }
        }
    }

    private func checkLaunchStaleness() {
        guard isEnabled, !isRunning else { return }
        let slotStart = Self.currentSlotStart()
        guard store?.isShowingCachedData != true,
              let generated = store?.feed?.generatedDate,
              generated >= slotStart
        else {
            runPipeline(trigger: "Stale feed on launch")
            return
        }
    }

    private func checkScheduledRun() {
        guard isEnabled, !isRunning,
              let token = Self.currentScheduleToken()
        else {
            return
        }
        guard defaults.string(forKey: Keys.lastScheduleAttempt) != token else {
            return
        }
        defaults.set(token, forKey: Keys.lastScheduleAttempt)
        runPipeline(trigger: "Scheduled run")
    }

    private func runPipeline(trigger: String) {
        guard !isRunning else {
            statusMessage = "newsbeat-digest is already running."
            return
        }

        let repositoryURL = URL(fileURLWithPath: repositoryPath)
        let executableURL = URL(fileURLWithPath: pythonPath)
        var isDirectory: ObjCBool = false
        guard FileManager.default.fileExists(
            atPath: repositoryURL.path,
            isDirectory: &isDirectory
        ), isDirectory.boolValue else {
            statusMessage = "Repository path does not exist."
            return
        }
        guard FileManager.default.isExecutableFile(atPath: executableURL.path) else {
            statusMessage = "Python executable is missing or not executable."
            return
        }

        let process = Process()
        let outputPipe = Pipe()
        process.executableURL = executableURL
        process.arguments = ["-m", "newsbeat_digest", "run"]
        process.currentDirectoryURL = repositoryURL
        process.standardOutput = outputPipe
        process.standardError = outputPipe

        var environment = ProcessInfo.processInfo.environment
        let key = KeychainStore.readAPIKey()
        if !key.isEmpty {
            environment["ANTHROPIC_API_KEY"] = key
        }
        process.environment = environment

        do {
            try process.run()
            self.process = process
            isRunning = true
            lastOutput = ""
            statusMessage = "\(trigger) started."

            Task { [weak self] in
                while process.isRunning {
                    try? await Task.sleep(for: .milliseconds(250))
                }
                let outputData = outputPipe.fileHandleForReading.readDataToEndOfFile()
                let output = String(decoding: outputData, as: UTF8.self)
                self?.finishRun(
                    status: process.terminationStatus,
                    output: output
                )
            }
        } catch {
            statusMessage = "Could not start newsbeat-digest: \(error.localizedDescription)"
        }
    }

    private func finishRun(status: Int32, output: String) {
        process = nil
        isRunning = false
        lastOutput = output.trimmingCharacters(in: .whitespacesAndNewlines)

        guard status == 0 else {
            statusMessage = "newsbeat-digest failed with exit status \(status)."
            return
        }

        statusMessage = "newsbeat-digest completed successfully."
        let localFeed = URL(fileURLWithPath: repositoryPath)
            .appending(path: "feed/digest.json")
        preferences.selectLocalFile(localFeed)
        Task {
            await store?.reload()
        }
    }

    // Four daytime runs, matching the systemd timer (07:07/11:07/16:07/21:07).
    private static let scheduleHours = [7, 11, 16, 21]

    private static func currentSlotHour(now: Date) -> Int? {
        let hour = Calendar.current.component(.hour, from: now)
        return scheduleHours.last { $0 <= hour }
    }

    private static func currentSlotStart(now: Date = .now) -> Date {
        let calendar = Calendar.current
        let slotHour = currentSlotHour(now: now) ?? 0
        return calendar.date(
            bySettingHour: slotHour,
            minute: 0,
            second: 0,
            of: now
        ) ?? now
    }

    private static func currentScheduleToken(now: Date = .now) -> String? {
        guard let slotHour = currentSlotHour(now: now) else { return nil }
        let day = now.formatted(.iso8601.year().month().day())
        return "\(day)-\(slotHour)"
    }

    private enum Keys {
        static let enabled = "host.enabled"
        static let repositoryPath = "host.repositoryPath"
        static let pythonPath = "host.pythonPath"
        static let lastScheduleAttempt = "host.lastScheduleAttempt"
    }
}
