import AppKit
import SwiftUI
import UniformTypeIdentifiers

struct SettingsSheet: View {
    @Environment(\.dismiss) private var dismiss
    @Environment(\.colorScheme) private var colorScheme
    @Bindable var model: AppViewModel

    @State private var winePath: String = ""
    @State private var dxmtSource: String = ""
    @State private var dxvkSource: String = ""
    @State private var bottleName: String = ""
    @State private var externalPrefix: String = ""
    @State private var useExternalPrefix: Bool = false
    @State private var validationMessage: String = ""

    var body: some View {
        VStack(spacing: 0) {
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    HStack {
                        Text("Backend Settings")
                            .font(.system(size: 26, weight: .bold, design: .rounded))
                        Spacer()
                    }

                    Text("Choose the Wine runtime you want, point the launcher at DXMT and DXVK, and keep the bottle details tucked here instead of in the main library.")
                        .foregroundStyle(.secondary)

                    VStack(alignment: .leading, spacing: 12) {
                        Text("Wine Runtime")
                            .font(.headline)
                            .foregroundStyle(themeForeground)

                        Picker("Wine Runtime", selection: Binding(
                            get: { model.selectedWineRuntimeID ?? "custom" },
                            set: { newValue in
                                guard newValue != "custom" else { return }
                                model.selectWineRuntime(id: newValue)
                                winePath = model.backendContext.winePath
                            }
                        )) {
                            ForEach(model.wineRuntimes) { runtime in
                                Text("\(runtime.name) • \(runtime.displaySubtitle)").tag(runtime.id)
                            }
                            Text("Custom Path").tag("custom")
                        }
                        .pickerStyle(.menu)

                        HStack(spacing: 10) {
                            Button("Import Wine App") {
                                model.importWineAppRuntime()
                                winePath = model.backendContext.winePath
                            }
                            Button("Register Binary") {
                                model.importWineBinaryRuntime()
                                winePath = model.backendContext.winePath
                            }
                            Button("Reveal Runtime Folder") {
                                model.revealManagedWineRuntimes()
                            }
                        }

                        Text("The launcher can keep multiple Wine builds around and switch the active one per app or bottle.")
                            .font(.footnote)
                            .foregroundStyle(themeMutedForeground)
                    }
                    .padding(16)
                    .background(themePanel)
                    .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))

                    Picker("Target Mode", selection: $useExternalPrefix) {
                        Text("Managed Bottle").tag(false)
                        Text("External Prefix").tag(true)
                    }
                    .pickerStyle(.segmented)

                    Group {
                        labeledField("Wine Path", text: $winePath, browseAction: {
                            if let path = pickPath(canChooseFiles: true, canChooseDirectories: false) {
                                winePath = path
                            }
                        })
                        labeledField("DXMT Source", text: $dxmtSource, browseAction: {
                            if let path = pickPath(canChooseFiles: true, canChooseDirectories: true) {
                                dxmtSource = path
                            }
                        })
                        labeledField("DXVK Source", text: $dxvkSource, browseAction: {
                            if let path = pickPath(canChooseFiles: true, canChooseDirectories: true) {
                                dxvkSource = path
                            }
                        })
                        VStack(alignment: .leading, spacing: 8) {
                            Text("Bottle Name")
                                .font(.subheadline.weight(.semibold))
                            Picker("Bottle Name", selection: $bottleName) {
                                ForEach(model.managedBottleNames, id: \.self) { name in
                                    Text(name).tag(name)
                                }
                            }
                            .pickerStyle(.menu)
                        }
                        .opacity(useExternalPrefix ? 0.45 : 1)
                        .disabled(useExternalPrefix)
                        labeledField("External Prefix", text: $externalPrefix, browseAction: {
                            if let path = pickPath(canChooseFiles: false, canChooseDirectories: true) {
                                externalPrefix = path
                            }
                        })
                            .opacity(useExternalPrefix ? 1 : 0.45)
                            .disabled(!useExternalPrefix)
                    }

                    if !validationMessage.isEmpty {
                        Text(validationMessage)
                            .font(.system(.footnote, design: .monospaced))
                            .foregroundStyle(themeMutedForeground)
                            .padding(12)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .background(themePanelRaised)
                            .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
                    }

                    Divider()

                    settingsOperationsPanel

                    settingsStatusPanel

                    settingsCurrentOperationPanel

                    settingsResultsPanel

                    settingsJobsPanel

                    settingsCommandPanel

                    settingsActivityPanel
                }
                .padding(24)
            }
            Divider()
            HStack {
                Button("Cancel") {
                    dismiss()
                }
                Spacer()
                Button("Test Settings") {
                    validationMessage = model.testSettings(
                        winePath: winePath,
                        dxmtSource: dxmtSource,
                        bottleName: bottleName,
                        externalPrefix: externalPrefix,
                        useExternalPrefix: useExternalPrefix
                    )
                    + "\n"
                    + model.validateDXVKSourceForWizard(dxvkSource).joined(separator: "\n")
                }
                Button("Save Settings") {
                    model.applySettings(
                        winePath: winePath,
                        dxmtSource: dxmtSource,
                        dxvkSource: dxvkSource,
                        bottleName: bottleName,
                        externalPrefix: externalPrefix,
                        useExternalPrefix: useExternalPrefix
                    )
                    dismiss()
                }
                .buttonStyle(.borderedProminent)
            }
            .padding(24)
        }
        .frame(width: 760, height: 760)
        .background(themeBackground)
        .task {
            model.refreshWineRuntimes()
            winePath = model.backendContext.winePath
            dxmtSource = model.backendContext.dxmtSource
            dxvkSource = model.backendContext.dxvkSource
            bottleName = model.backendContext.bottleName
            externalPrefix = model.backendContext.externalPrefix ?? ""
            useExternalPrefix = !(model.backendContext.externalPrefix ?? "").isEmpty
        }
    }

    private func labeledField(_ title: String, text: Binding<String>, browseAction: (() -> Void)? = nil) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title)
                .font(.subheadline.weight(.semibold))
            HStack(spacing: 10) {
                TextField(title, text: text)
                    .textFieldStyle(.roundedBorder)
                if let browseAction {
                    Button("Browse") {
                        browseAction()
                    }
                }
            }
        }
    }

    private func pickPath(canChooseFiles: Bool, canChooseDirectories: Bool) -> String? {
        let panel = NSOpenPanel()
        panel.canChooseFiles = canChooseFiles
        panel.canChooseDirectories = canChooseDirectories
        panel.allowsMultipleSelection = false
        panel.canCreateDirectories = false
        return panel.runModal() == .OK ? panel.url?.path : nil
    }

    private var settingsOperationsPanel: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Operations")
                .font(.headline)
                .foregroundStyle(themeForeground)
            ForEach(model.operationCards) { operation in
                Button {
                    if operation.kind == .winetricks {
                        dismiss()
                        model.openWinetricksAfterSettingsDismiss()
                    } else {
                        dismiss()
                        model.performAfterSettingsDismiss(operation)
                    }
                } label: {
                    HStack(alignment: .top, spacing: 12) {
                        Image(systemName: operation.symbolName)
                            .font(.title3.weight(.semibold))
                            .frame(width: 32)
                        VStack(alignment: .leading, spacing: 4) {
                            Text(operation.title)
                                .fontWeight(.semibold)
                                .foregroundStyle(themeForeground)
                            Text(operation.detail)
                                .font(.subheadline)
                                .foregroundStyle(themeMutedForeground)
                        }
                        Spacer()
                        Image(systemName: "arrow.right")
                            .foregroundStyle(themeMutedForeground)
                    }
                    .padding(14)
                    .background(themePanel)
                    .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
                }
                .buttonStyle(.plain)
                .disabled(model.isBusy)
                .opacity(model.isBusy ? 0.65 : 1)
            }
        }
    }

    private var settingsStatusPanel: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Backend Target")
                .font(.headline)
                .foregroundStyle(themeForeground)
            Text(model.settingsSummary)
                .font(.subheadline)
                .foregroundStyle(themeMutedForeground)
                .fixedSize(horizontal: false, vertical: true)
            Text("Wine Runtime: \(model.wineRuntimeSummary)")
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(themeForeground)
            Text("Wine Path: \(model.backendContext.winePath)")
                .font(.system(.footnote, design: .monospaced))
                .foregroundStyle(themeMutedForeground)
                .textSelection(.enabled)
            Text("DXMT: \(model.backendContext.dxmtSource)")
                .font(.system(.footnote, design: .monospaced))
                .foregroundStyle(themeMutedForeground)
                .textSelection(.enabled)
        }
        .padding(16)
        .background(themePanel)
        .clipShape(RoundedRectangle(cornerRadius: 20, style: .continuous))
    }

    private var settingsResultsPanel: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Structured Results")
                .font(.headline)
                .foregroundStyle(themeForeground)

            if let doctor = model.latestDoctorResult {
                structuredResultCard(
                    title: "Latest Doctor",
                    result: doctor,
                    accent: healthAccentColor(for: doctor.worstStatus)
                )
            }

            if let setup = model.latestSetupResult {
                structuredResultCard(
                    title: "Latest Setup",
                    result: setup,
                    accent: Color(hex: "#6DBB7A")
                )
            }

            if model.latestDoctorResult == nil && model.latestSetupResult == nil {
                Text("Run an environment check or setup pass to populate structured backend state here.")
                    .font(.subheadline)
                    .foregroundStyle(themeMutedForeground)
            }
        }
        .padding(16)
        .background(themePanel)
        .clipShape(RoundedRectangle(cornerRadius: 20, style: .continuous))
    }

    private var settingsCurrentOperationPanel: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Current Operation")
                .font(.headline)
                .foregroundStyle(themeForeground)

            if let job = model.currentOperationJob {
                jobRow(job)

                if let result = model.currentOperationResult {
                    structuredResultCard(
                        title: "Live Details",
                        result: result,
                        accent: healthAccentColor(for: result.worstStatus)
                    )
                }
            } else {
                Text("No active backend work right now.")
                    .font(.subheadline)
                    .foregroundStyle(themeMutedForeground)
            }
        }
        .padding(16)
        .background(themePanel)
        .clipShape(RoundedRectangle(cornerRadius: 20, style: .continuous))
    }

    private var settingsJobsPanel: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Jobs")
                .font(.headline)
                .foregroundStyle(themeForeground)

            if model.activeBackendJobs.isEmpty == false {
                VStack(alignment: .leading, spacing: 8) {
                    Text("Active")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(themeForeground)
                    ForEach(model.activeBackendJobs) { job in
                        jobRow(job)
                    }
                }
            }

            if model.recentBackendJobs.isEmpty == false {
                VStack(alignment: .leading, spacing: 8) {
                    Text("Recent")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(themeForeground)
                    ForEach(Array(model.recentBackendJobs.prefix(6))) { job in
                        jobRow(job)
                    }
                }
            }

            if model.activeBackendJobs.isEmpty && model.recentBackendJobs.isEmpty {
                Text("No backend jobs recorded yet.")
                    .font(.subheadline)
                    .foregroundStyle(themeMutedForeground)
            }
        }
        .padding(16)
        .background(themePanel)
        .clipShape(RoundedRectangle(cornerRadius: 20, style: .continuous))
    }

    @ViewBuilder
    private func jobRow(_ job: BackendJob) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(alignment: .top, spacing: 12) {
                Circle()
                    .fill(jobAccentColor(for: job.status))
                    .frame(width: 10, height: 10)
                    .padding(.top, 5)

                VStack(alignment: .leading, spacing: 4) {
                    Text(job.action)
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(themeForeground)
                    Text(job.message)
                        .font(.subheadline)
                        .foregroundStyle(themeMutedForeground)
                        .fixedSize(horizontal: false, vertical: true)
                    HStack(spacing: 8) {
                        Text(job.status.rawValue.capitalized)
                            .font(.caption.weight(.semibold))
                            .foregroundStyle(jobAccentColor(for: job.status))
                        if let completedSteps = job.completedSteps, let totalSteps = job.totalSteps, totalSteps > 0 {
                            Text("\(completedSteps)/\(totalSteps) phases")
                                .font(.caption)
                                .foregroundStyle(themeMutedForeground)
                        }
                    }
                }
            }

            if let progress = job.progress {
                ProgressView(value: progress)
                    .tint(jobAccentColor(for: job.status))
            }
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(themePanelRaised)
        .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
    }

    private var settingsCommandPanel: some View {
        VStack(alignment: .leading, spacing: 10) {
            DisclosureGroup(
                isExpanded: Binding(
                    get: { model.expandedDebugSections.contains(.bridgeCommands) },
                    set: { isExpanded in
                        if isExpanded {
                            model.expandedDebugSections.insert(.bridgeCommands)
                        } else {
                            model.expandedDebugSections.remove(.bridgeCommands)
                        }
                    }
                )
            ) {
                VStack(alignment: .leading, spacing: 10) {
                    ForEach(model.bridgeCommands) { command in
                        VStack(alignment: .leading, spacing: 4) {
                            Text(command.title)
                                .font(.subheadline.weight(.semibold))
                                .foregroundStyle(themeForeground)
                            Text(command.command)
                                .font(.system(.footnote, design: .monospaced))
                                .foregroundStyle(themeMutedForeground)
                                .textSelection(.enabled)
                        }
                        .padding(12)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(themePanelRaised)
                        .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
                    }
                }
                .padding(.top, 8)
            } label: {
                Text("Backend Bridge")
                    .font(.headline)
                    .foregroundStyle(themeForeground)
            }
        }
        .padding(16)
        .background(themePanel)
        .clipShape(RoundedRectangle(cornerRadius: 20, style: .continuous))
    }

    private var settingsActivityPanel: some View {
        VStack(alignment: .leading, spacing: 10) {
            DisclosureGroup(
                isExpanded: Binding(
                    get: { model.expandedDebugSections.contains(.activityLog) },
                    set: { isExpanded in
                        if isExpanded {
                            model.expandedDebugSections.insert(.activityLog)
                        } else {
                            model.expandedDebugSections.remove(.activityLog)
                        }
                    }
                )
            ) {
                Text(model.activityLog)
                    .font(.system(.footnote, design: .monospaced))
                    .foregroundStyle(themeMutedForeground)
                    .textSelection(.enabled)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.top, 8)
            } label: {
                Text("Activity Log")
                    .font(.headline)
                    .foregroundStyle(themeForeground)
            }
        }
        .padding(16)
        .background(themePanel)
        .clipShape(RoundedRectangle(cornerRadius: 20, style: .continuous))
    }

    @ViewBuilder
    private func structuredResultCard(title: String, result: BackendStructuredResult, accent: Color) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text(title)
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(themeForeground)
                Spacer()
                if let worstStatus = result.worstStatus {
                    Text(worstStatus.uppercased())
                        .font(.caption.weight(.bold))
                        .foregroundStyle(accent)
                }
            }

            if let target = result.target, !target.isEmpty {
                Text(target)
                    .font(.system(.footnote, design: .monospaced))
                    .foregroundStyle(themeMutedForeground)
                    .textSelection(.enabled)
            }

            if let root = result.root, !root.isEmpty {
                Text(root)
                    .font(.system(.footnote, design: .monospaced))
                    .foregroundStyle(themeMutedForeground)
                    .textSelection(.enabled)
            }

            if let completedSteps = result.completedSteps, let totalSteps = result.totalSteps, totalSteps > 0 {
                VStack(alignment: .leading, spacing: 6) {
                    HStack {
                        Text("Progress")
                            .font(.caption.weight(.semibold))
                            .foregroundStyle(themeForeground)
                        Spacer()
                        Text("\(completedSteps)/\(totalSteps) phases")
                            .font(.caption)
                            .foregroundStyle(themeMutedForeground)
                    }
                    ProgressView(value: Double(completedSteps), total: Double(totalSteps))
                        .tint(accent)
                }
            }

            if result.fixes.isEmpty == false {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Applied Fixes")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(themeForeground)
                    ForEach(Array(result.fixes.enumerated()), id: \.offset) { entry in
                        Text(entry.element)
                            .font(.footnote)
                            .foregroundStyle(themeMutedForeground)
                    }
                }
            }

            if result.steps.isEmpty == false {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Steps")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(themeForeground)
                    ForEach(result.steps) { step in
                        HStack(alignment: .top, spacing: 8) {
                            Circle()
                                .fill(step.status.lowercased() == "ok" ? Color(hex: "#6DBB7A") : Color(hex: "#8A948C"))
                                .frame(width: 8, height: 8)
                                .padding(.top, 4)
                            Text(step.name)
                                .font(.footnote)
                                .foregroundStyle(themeMutedForeground)
                            Spacer()
                            Text(step.status.uppercased())
                                .font(.caption2.weight(.semibold))
                                .foregroundStyle(themeMutedForeground)
                        }
                    }
                }
            }

            if result.checks.isEmpty == false {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Checks")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(themeForeground)
                    ForEach(Array(result.checks.prefix(8))) { check in
                        HStack(alignment: .top, spacing: 8) {
                            Circle()
                                .fill(healthAccentColor(for: check.status))
                                .frame(width: 8, height: 8)
                                .padding(.top, 4)
                            VStack(alignment: .leading, spacing: 2) {
                                Text(check.name)
                                    .font(.footnote.weight(.semibold))
                                    .foregroundStyle(themeForeground)
                                Text(check.detail)
                                    .font(.caption)
                                    .foregroundStyle(themeMutedForeground)
                                    .fixedSize(horizontal: false, vertical: true)
                            }
                        }
                    }
                    if result.checks.count > 8 {
                        Text("+ \(result.checks.count - 8) more checks in activity log")
                            .font(.caption)
                            .foregroundStyle(themeMutedForeground)
                    }
                }
            }

            if result.signals.isEmpty == false {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Detected Signals")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(themeForeground)
                    ForEach(Array(result.signals.prefix(6))) { signal in
                        VStack(alignment: .leading, spacing: 2) {
                            Text(signal.key)
                                .font(.footnote.weight(.semibold))
                                .foregroundStyle(themeForeground)
                            Text(signal.detail)
                                .font(.caption)
                                .foregroundStyle(themeMutedForeground)
                            Text(signal.path)
                                .font(.system(.caption2, design: .monospaced))
                                .foregroundStyle(themeMutedForeground)
                        }
                    }
                }
            }

            if result.recommendations.isEmpty == false {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Recommendations")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(themeForeground)
                    ForEach(result.recommendations) { recommendation in
                        VStack(alignment: .leading, spacing: 2) {
                            Text(recommendation.verb)
                                .font(.footnote.weight(.semibold))
                                .foregroundStyle(themeForeground)
                            Text(recommendation.reason)
                                .font(.caption)
                                .foregroundStyle(themeMutedForeground)
                        }
                    }
                }
            }

            if result.warnings.isEmpty == false || result.errors.isEmpty == false {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Messages")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(themeForeground)
                    ForEach(Array(result.warnings.enumerated()), id: \.offset) { entry in
                        Text(entry.element)
                            .font(.caption)
                            .foregroundStyle(Color.orange)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                    ForEach(Array(result.errors.enumerated()), id: \.offset) { entry in
                        Text(entry.element)
                            .font(.caption)
                            .foregroundStyle(Color.red)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }
            }
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(themePanelRaised)
        .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
    }

    private func healthAccentColor(for status: String?) -> Color {
        switch status?.lowercased() {
        case "fail":
            return Color.red
        case "warn":
            return Color.orange
        case "ok":
            return Color(hex: "#6DBB7A")
        default:
            return Color(hex: "#8A948C")
        }
    }

    private func jobAccentColor(for status: BackendJobStatus) -> Color {
        switch status {
        case .started:
            return Color(hex: "#6DBB7A")
        case .completed:
            return Color(hex: "#6DBB7A")
        case .failed:
            return Color.red
        case .queued:
            return Color(hex: "#8A948C")
        }
    }

    private var themeBackground: Color { colorScheme == .dark ? Color(hex: "#20231F") : Color(hex: "#EEF3EC") }
    private var themePanel: Color { colorScheme == .dark ? Color(hex: "#2A302C") : Color(hex: "#F7FBF5") }
    private var themePanelRaised: Color { colorScheme == .dark ? Color(hex: "#353D38") : Color(hex: "#DEE8DE") }
    private var themeForeground: Color { colorScheme == .dark ? Color(hex: "#D4DBD4") : Color(hex: "#162019") }
    private var themeMutedForeground: Color { colorScheme == .dark ? Color(hex: "#AEB7AF") : Color(hex: "#55635A") }
}
