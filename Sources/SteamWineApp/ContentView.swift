import AppKit
import SwiftUI
import UniformTypeIdentifiers

struct ContentView: View {
    @Bindable var model: AppViewModel
    @Environment(\.colorScheme) private var colorScheme
    @State private var draggedGame: LibraryGame?

    var body: some View {
        NavigationSplitView {
            sidebar
        } detail: {
            library
        }
        .navigationSplitViewStyle(.prominentDetail)
        .sheet(isPresented: $model.isShowingSettings) {
            SettingsSheet(model: model)
        }
        .sheet(isPresented: $model.isShowingGameSettings) {
            if let game = model.editingGame {
                GameSettingsSheet(model: model, game: game)
            }
        }
        .sheet(isPresented: $model.isShowingGameDetails) {
            if let game = model.editingGame {
                GameDetailsSheet(model: model, game: game)
            }
        }
        .sheet(isPresented: $model.isShowingLogViewer) {
            LogViewerSheet(model: model)
        }
        .sheet(isPresented: $model.isShowingWinetricks) {
            WinetricksSheet(model: model)
        }
    }

    private var columns: [GridItem] {
        [
            GridItem(
                .adaptive(
                    minimum: 360,
                    maximum: 380
                ),
                spacing: 24
            ),
        ]
    }

    private var sidebar: some View {
        VStack(spacing: 0) {
            HStack(spacing: 12) {
                if let image = moduleNSImage(named: "NASE Logo") {
                    Image(nsImage: image)
                        .resizable()
                        .scaledToFit()
                        .frame(width: 34, height: 34)
                }
                VStack(alignment: .leading, spacing: 2) {
                    Text("NASE")
                        .font(.headline.weight(.bold))
                    Text("Game Launcher")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                Spacer()
            }
            .padding(16)

            Divider()

            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    ForEach(model.sidebarSections) { section in
                        VStack(alignment: .leading, spacing: 6) {
                            Text(section.title)
                                .font(.caption.weight(.semibold))
                                .foregroundStyle(.secondary)
                                .padding(.horizontal, 16)
                            ForEach(section.runners) { runner in
                                Button {
                                    model.selectRunner(runner)
                                } label: {
                                    SidebarRow(
                                        runner: runner,
                                        isSelected: model.selectedRunner == runner
                                    )
                                }
                                .buttonStyle(.plain)
                                .padding(.horizontal, 8)
                                .frame(maxWidth: .infinity, alignment: .leading)
                            }
                        }
                    }
                }
                .padding(.vertical, 12)
            }

            Divider()

            Button {
                model.openSettings()
            } label: {
                Label("Settings", systemImage: "slider.horizontal.3")
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.horizontal, 14)
                    .padding(.vertical, 12)
            }
            .buttonStyle(.plain)
            .background(themePanel)
        }
        .background(themeSidebar)
        .navigationTitle("Sources")
    }

    private var library: some View {
        VStack(spacing: 0) {
            HStack(alignment: .center, spacing: 14) {
                VStack(alignment: .leading, spacing: 4) {
                    Text(model.selectedRunner?.rawValue ?? "Library")
                        .font(.system(size: 24, weight: .bold, design: .rounded))
                    Text(model.settingsSummary)
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                }
                .frame(minWidth: 220, alignment: .leading)

                TextField("Filter the library", text: $model.searchText)
                    .textFieldStyle(.roundedBorder)
                    .frame(maxWidth: 340)

                Menu {
                    ForEach(LibrarySortOption.allCases) { option in
                        Button(option.rawValue) {
                            model.sortOption = option
                        }
                    }
                } label: {
                    toolbarControlLabel(
                        title: "Sort",
                        value: model.sortOption.rawValue,
                        systemImage: "arrow.up.arrow.down"
                    )
                }
                .menuStyle(.borderlessButton)

                Menu {
                    Button("All Collections") {
                        model.collectionFilter = nil
                    }
                    ForEach(GameCollection.allCases.filter { $0 != .none }) { collection in
                        Button(collection.rawValue) {
                            model.collectionFilter = collection
                        }
                    }
                } label: {
                    toolbarControlLabel(
                        title: nil,
                        value: model.collectionFilter?.rawValue ?? "Collections",
                        systemImage: "line.3.horizontal.decrease.circle"
                    )
                }
                .menuStyle(.borderlessButton)

                if model.selectedRunner == .home {
                    Menu {
                        ForEach(LibrarySourceFilter.allCases) { option in
                            Button(option.rawValue) {
                                model.sourceFilter = option
                            }
                        }
                    } label: {
                        toolbarControlLabel(
                            title: nil,
                            value: model.sourceFilter.rawValue,
                            systemImage: "square.grid.2x2"
                        )
                    }
                    .menuStyle(.borderlessButton)
                }

                Spacer(minLength: 0)
                if model.selectedRunner == .steam {
                    Button {
                        model.perform(
                            OperationCard(
                                kind: .openSteam,
                                title: "Open Steam",
                                detail: "Launch Windows Steam without waiting for it to exit.",
                                symbolName: "play.circle"
                            )
                        )
                    } label: {
                        toolbarButtonLabel("Open Steam", systemImage: "play.circle")
                    }
                    .buttonStyle(.plain)

                    Button {
                        model.refreshGames()
                    } label: {
                        toolbarButtonLabel("Refresh", systemImage: "arrow.clockwise")
                    }
                    .buttonStyle(.plain)
                }
                if model.shouldShowAddButton {
                    if model.shouldShowWineAddMenu {
                        Menu {
                            Button("Add Windows Game") {
                                model.performPrimaryAddAction()
                            }
                            Button("Open Installer") {
                                model.openWineInstaller()
                            }
                        } label: {
                            toolbarButtonLabel("Add", systemImage: "plus")
                        }
                        .menuStyle(.borderlessButton)
                    } else {
                        Button {
                            model.performPrimaryAddAction()
                        } label: {
                            toolbarButtonLabel(model.selectedRunnerActionTitle, systemImage: "plus")
                        }
                        .buttonStyle(.plain)
                    }
                }
            }
            .padding(.horizontal, 20)
            .padding(.top, 16)
            .padding(.bottom, 16)
            .background(themeToolbar)

            ScrollView {
                if model.filteredGames.isEmpty {
                    EmptyLibraryState(
                        title: model.selectedRunner?.rawValue ?? "Library",
                        message: model.libraryEmptyMessage,
                        showsActions: model.shouldShowSteamEmptyStateActions,
                        isBusy: model.isBusy,
                        onOpenSettings: {
                            model.openSettings()
                        },
                        onRefresh: {
                            model.refreshGames()
                        }
                    )
                    .padding(20)
                } else {
                    LazyVGrid(columns: columns, spacing: 24) {
                        ForEach(model.filteredGames) { game in
                            GameCard(
                                game: game,
                                isSelected: model.selectedGame?.id == game.id,
                                isBusy: model.isBusy,
                                isDragging: draggedGame?.pinID == game.pinID,
                                collection: model.settings(for: game).collection,
                                onLaunch: {
                                    model.launch(game)
                                },
                                isPinned: model.isPinned(game),
                                onTogglePin: {
                                    model.togglePin(for: game)
                                },
                                onOpenStore: {
                                    model.openSteamStorePage(for: game)
                                },
                                onRevealFiles: {
                                    model.revealLocalFiles(for: game)
                                },
                                onOpenDetails: {
                                    model.openGameDetails(for: game)
                                },
                                onGameSettings: {
                                    model.openGameSettings(for: game)
                                },
                                onRevealLogs: {
                                    model.openLogViewer(for: game)
                                },
                                onDebugLaunch: {
                                    model.debugLaunch(game)
                                },
                                onChangeIcon: {
                                    model.changeAppIcon()
                                },
                                onRemoveFromLibrary: {
                                    model.removeGameFromLibrary(game)
                                }
                            )
                                .onTapGesture {
                                    model.selectGame(game)
                                }
                                .onDrag {
                                    draggedGame = game
                                    return NSItemProvider(object: game.pinID as NSString)
                                } preview: {
                                    DragBadge(title: game.title)
                                }
                                .onDrop(
                                    of: [UTType.text],
                                    delegate: GameDropDelegate(
                                        targetGame: game,
                                        draggedGame: $draggedGame,
                                        model: model
                                    )
                                )
                        }
                    }
                    .padding(24)
                }
            }
            .background(themeBackground)
        }
        .navigationTitle(model.selectedRunner?.rawValue ?? "Library")
        .task {
            model.initialLoad()
        }
    }

    private var themeBackground: Color { colorScheme == .dark ? Color(hex: "#20231F") : Color(hex: "#EEF3EC") }
    private var themeSidebar: Color { colorScheme == .dark ? Color(hex: "#181B18") : Color(hex: "#E4ECE3") }
    private var themeToolbar: Color { colorScheme == .dark ? Color(hex: "#181B18") : Color(hex: "#E8EEE7") }
    private var themePanel: Color { colorScheme == .dark ? Color(hex: "#2A302C") : Color(hex: "#F7FBF5") }
    private var themePanelRaised: Color { colorScheme == .dark ? Color(hex: "#353D38") : Color(hex: "#DEE8DE") }

    @ViewBuilder
    private func toolbarButtonLabel(_ title: String, systemImage: String) -> some View {
        Label(title, systemImage: systemImage)
            .font(.system(size: 14, weight: .semibold))
            .foregroundStyle(colorScheme == .dark ? Color(hex: "#E6ECE6") : Color(hex: "#162019"))
            .lineLimit(1)
            .minimumScaleFactor(0.9)
            .padding(.horizontal, 12)
            .frame(height: 34)
            .background(themePanelRaised)
            .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: 8, style: .continuous)
                    .stroke(colorScheme == .dark ? Color.white.opacity(0.08) : Color.black.opacity(0.08), lineWidth: 1)
            )
    }

    @ViewBuilder
    private func toolbarControlLabel(title: String?, value: String, systemImage: String) -> some View {
        HStack(spacing: 10) {
            Image(systemName: systemImage)
                .font(.system(size: 13, weight: .semibold))
            if let title {
                Text(title)
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundStyle(colorScheme == .dark ? Color(hex: "#E6ECE6") : Color(hex: "#162019"))
                    .lineLimit(1)
                    .minimumScaleFactor(0.9)
            }
            Text(value)
                .font(.system(size: 14, weight: .semibold))
                .foregroundStyle(colorScheme == .dark ? Color(hex: "#E6ECE6") : Color(hex: "#162019"))
                .lineLimit(1)
                .minimumScaleFactor(0.9)
            Image(systemName: "chevron.down")
                .font(.system(size: 11, weight: .bold))
                .foregroundStyle(colorScheme == .dark ? Color(hex: "#AEB7AF") : Color(hex: "#55635A"))
        }
        .padding(.horizontal, 12)
        .frame(height: 34)
        .background(themePanelRaised)
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .stroke(colorScheme == .dark ? Color.white.opacity(0.08) : Color.black.opacity(0.08), lineWidth: 1)
        )
    }
}

private struct SettingsSheet: View {
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

private struct SetupWizardSheet: View {
    @Environment(\.dismiss) private var dismiss
    @Environment(\.colorScheme) private var colorScheme
    @Bindable var model: AppViewModel

    @State private var selectedStep: SetupWizardStep = .welcome
    @State private var winePath: String = ""
    @State private var dxmtSource: String = ""
    @State private var dxvkSource: String = ""
    @State private var bottleName: String = ""
    @State private var downloadStatusMessage: String = ""
    @State private var isDownloadingDXMT: Bool = false

    private let orderedSteps = SetupWizardStep.allCases

    var body: some View {
        HStack(spacing: 0) {
            VStack(alignment: .leading, spacing: 16) {
                Text("Setup Wizard")
                    .font(.system(size: 26, weight: .bold, design: .rounded))
                Text("This gets a new machine from zero to a managed Steam + Metal setup without making the user piece the backend together manually.")
                    .font(.subheadline)
                    .foregroundStyle(themeMutedForeground)

                VStack(alignment: .leading, spacing: 8) {
                    ForEach(orderedSteps) { step in
                        Button {
                            selectedStep = step
                        } label: {
                            HStack(spacing: 10) {
                                Circle()
                                    .fill(step == selectedStep ? themePrimary : stepAccent(for: step))
                                    .frame(width: 10, height: 10)
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(step.rawValue)
                                        .font(.subheadline.weight(.semibold))
                                        .foregroundStyle(themeForeground)
                                    Text(step.subtitle)
                                        .font(.caption)
                                        .foregroundStyle(themeMutedForeground)
                                }
                                Spacer()
                            }
                            .padding(.horizontal, 12)
                            .padding(.vertical, 10)
                            .background(step == selectedStep ? themePanelRaised : Color.clear)
                            .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
                        }
                        .buttonStyle(.plain)
                    }
                }

                Spacer()
            }
            .frame(width: 250)
            .padding(24)
            .background(themeSidebar)

            Divider()

            VStack(spacing: 0) {
                ScrollView {
                    VStack(alignment: .leading, spacing: 18) {
                        requirementsChecklist
                        stepBody
                    }
                    .padding(24)
                }

                Divider()

                HStack {
                    Button("Close") {
                        model.closeSetupWizard()
                        dismiss()
                    }

                    Spacer()

                    if let previousStep = previousStep {
                        Button("Back") {
                            selectedStep = previousStep
                        }
                    }

                    if let nextStep = nextStep {
                        Button("Next") {
                            selectedStep = nextStep
                        }
                        .buttonStyle(.borderedProminent)
                    } else {
                        Button("Done") {
                            model.closeSetupWizard()
                            dismiss()
                        }
                        .buttonStyle(.borderedProminent)
                    }
                }
                .padding(24)
            }
            .background(themeBackground)
        }
        .frame(width: 980, height: 720)
        .task {
            winePath = model.backendContext.winePath
            dxmtSource = model.backendContext.dxmtSource
            dxvkSource = model.backendContext.dxvkSource
            bottleName = model.backendContext.bottleName
        }
    }

    @ViewBuilder
    private var stepBody: some View {
        switch selectedStep {
        case .welcome:
            wizardCard(title: "What this flow does", subtitle: "The wizard is built to get someone new to Wine unstuck quickly.") {
                VStack(alignment: .leading, spacing: 12) {
                    setupBullet("Detect Wine and tell you exactly what to install if it is missing.")
                    setupBullet("Detect Winetricks and do the same.")
                    setupBullet("Pick the DXMT payload we use for the managed Metal path.")
                    setupBullet("Create a managed bottle under ~/Library/Application Support/MySteamWine.")
                    setupBullet("Install Steam into that bottle and prepare it for launch.")
                    Text("DXVK remains available later as a per-game compatibility choice. The guided setup flow is centered on the managed DXMT/Metal path we have been validating.")
                        .foregroundStyle(themeMutedForeground)
                }
            }

        case .wine:
            wizardCard(title: "Wine Detection", subtitle: model.detectedWinePathStatus(winePath)) {
                VStack(alignment: .leading, spacing: 14) {
                    labeledField("Wine Path", text: $winePath) {
                        if let path = pickPath(canChooseFiles: true, canChooseDirectories: false) {
                            winePath = path
                        }
                    }
                    guidanceBlock(
                        title: "Install Guidance",
                        lines: [
                            "1. Install Rosetta 2 if needed: `softwareupdate --install-rosetta --agree-to-license`",
                            "2. Install Wine Stable: `brew install --cask wine-stable`",
                            "3. Verify: `which wine` and `wine --version`",
                        ]
                    )
                }
            }

        case .winetricks:
            wizardCard(title: "Winetricks Detection", subtitle: model.detectedWinetricksStatus()) {
                guidanceBlock(
                    title: "Install Guidance",
                    lines: [
                        "Install Winetricks with Homebrew: `brew install winetricks`",
                        "Verify the install: `winetricks --version`",
                        "The setup flow uses Winetricks to install Steam into the managed bottle.",
                    ]
                )
            }

        case .graphics:
            wizardCard(title: "Graphics Stack", subtitle: "Pick or download the graphics payloads the app can manage for you.") {
                VStack(alignment: .leading, spacing: 14) {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Managed DXMT Path")
                            .font(.subheadline.weight(.semibold))
                        labeledField("DXMT Source", text: $dxmtSource) {
                            if let path = pickPath(canChooseFiles: true, canChooseDirectories: true) {
                                dxmtSource = path
                            }
                        }
                        HStack(spacing: 10) {
                            Button {
                                Task {
                                    await downloadDXMT()
                                }
                            } label: {
                                Label("Download DXMT 0.71", systemImage: "arrow.down.circle")
                            }
                            .buttonStyle(.borderedProminent)
                            .disabled(isDownloadingDXMT)

                            if isDownloadingDXMT {
                                ProgressView()
                                    .controlSize(.small)
                            }
                        }
                        statusBlock(lines: model.validateDXMTSourceForWizard(dxmtSource))
                    }

                    VStack(alignment: .leading, spacing: 8) {
                        Text("Optional DXVK Path")
                            .font(.subheadline.weight(.semibold))
                        labeledField("DXVK Source", text: $dxvkSource) {
                            if let path = pickPath(canChooseFiles: true, canChooseDirectories: true) {
                                dxvkSource = path
                            }
                        }
                        Text("DXVK is not part of the core Steam + Metal setup flow, but it is still useful later for per-game compatibility. This gives non-technical users a place to prepare it without going back to the terminal.")
                            .foregroundStyle(themeMutedForeground)
                        HStack(spacing: 10) {
                            Button {
                                Task {
                                    await downloadDXVK()
                                }
                            } label: {
                                Label("Download DXVK 2.3", systemImage: "arrow.down.circle")
                            }
                            .buttonStyle(.bordered)
                            .disabled(isDownloadingDXMT)
                        }
                        statusBlock(lines: model.validateDXVKSourceForWizard(dxvkSource))
                        Button {
                            model.installDXVKFromWizard(
                                winePath: winePath,
                                dxmtSource: dxmtSource,
                                dxvkSource: dxvkSource,
                                bottleName: bottleName
                            )
                        } label: {
                            Label("Install DXVK Into This Bottle", systemImage: "shippingbox")
                        }
                        .buttonStyle(.bordered)
                        .disabled(!canInstallDXVK || model.isBusy)
                    }

                    if !downloadStatusMessage.isEmpty {
                        Text(downloadStatusMessage)
                            .font(.subheadline)
                            .foregroundStyle(themeMutedForeground)
                            .padding(12)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .background(themePanelRaised)
                            .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
                    }
                }
            }

        case .bottle:
            wizardCard(title: "Managed Bottle", subtitle: "Choose the bottle the app should create and maintain for Steam.") {
                VStack(alignment: .leading, spacing: 14) {
                    labeledField("Bottle Name", text: $bottleName, browseAction: nil)
                    Text("The prefix will live under `~/Library/Application Support/MySteamWine/bottles/<BottleName>`.")
                        .font(.subheadline)
                        .foregroundStyle(themeMutedForeground)
                    if !model.managedBottleNames.isEmpty {
                        VStack(alignment: .leading, spacing: 8) {
                            Text("Existing Bottles")
                                .font(.subheadline.weight(.semibold))
                            ScrollView(.horizontal, showsIndicators: false) {
                                HStack(spacing: 8) {
                                    ForEach(model.managedBottleNames, id: \.self) { name in
                                        Button(name) {
                                            bottleName = name
                                        }
                                        .buttonStyle(.bordered)
                                    }
                                }
                            }
                        }
                    }
                }
            }

        case .steam:
            wizardCard(title: "Steam Setup", subtitle: "Run the managed Steam + Metal setup flow using the values above.") {
                VStack(alignment: .leading, spacing: 14) {
                    statusBlock(lines: [
                        model.detectedWinePathStatus(winePath),
                        model.detectedWinetricksStatus(),
                    ] + model.validateDXMTSourceForWizard(dxmtSource))

                    Button {
                        model.runSetupWizard(
                            winePath: winePath,
                            dxmtSource: dxmtSource,
                            dxvkSource: dxvkSource,
                            bottleName: bottleName
                        )
                    } label: {
                        Label("Run Setup", systemImage: "hammer")
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.borderedProminent)
                    .disabled(!model.setupWizardCanRun(winePath: winePath, dxmtSource: dxmtSource, bottleName: bottleName) || model.isBusy)

                    if let job = model.currentOperationJob, job.action == "Setup Metal" {
                        VStack(alignment: .leading, spacing: 10) {
                            Text(job.message)
                                .font(.subheadline.weight(.semibold))
                            if let progress = job.progress {
                                ProgressView(value: progress)
                                    .tint(themePrimary)
                            }
                            if let completedSteps = job.completedSteps, let totalSteps = job.totalSteps, totalSteps > 0 {
                                Text("\(completedSteps) / \(totalSteps) phases")
                                    .font(.caption)
                                    .foregroundStyle(themeMutedForeground)
                            }
                        }
                        .padding(14)
                        .background(themePanelRaised)
                        .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
                    }
                }
            }

        case .finish:
            wizardCard(title: "Finish", subtitle: finishSubtitle) {
                VStack(alignment: .leading, spacing: 14) {
                    guideBlock
                    if let setup = model.latestSetupResult {
                        statusBlock(lines: setup.steps.map { "\($0.status.uppercased()): \($0.name)" } + setup.warnings + setup.errors)
                    } else {
                        Text("Run Setup first, then come back here to review the result and launch Steam.")
                            .foregroundStyle(themeMutedForeground)
                    }

                    HStack(spacing: 10) {
                        Button {
                            model.perform(
                                OperationCard(
                                    kind: .openSteam,
                                    title: "Open Steam",
                                    detail: "Launch Windows Steam without waiting for it to exit.",
                                    symbolName: "play.circle"
                                )
                            )
                        } label: {
                            Label("Open Steam", systemImage: "play.circle")
                        }
                        .buttonStyle(.borderedProminent)
                        .disabled(model.latestSetupResult == nil)

                        Button("Open Settings") {
                            model.closeSetupWizard()
                            dismiss()
                            model.openSettings()
                        }
                        .buttonStyle(.bordered)
                    }
                }
            }
        }
    }

    private var previousStep: SetupWizardStep? {
        guard let index = orderedSteps.firstIndex(of: selectedStep), index > 0 else { return nil }
        return orderedSteps[index - 1]
    }

    private var nextStep: SetupWizardStep? {
        guard let index = orderedSteps.firstIndex(of: selectedStep), index < orderedSteps.count - 1 else { return nil }
        return orderedSteps[index + 1]
    }

    private var finishSubtitle: String {
        if let job = model.recentBackendJobs.first(where: { $0.action == "Setup Metal" }) {
            switch job.status {
            case .completed:
                return "Setup finished. Steam should now be ready in the managed bottle."
            case .failed:
                return "Setup failed. Review the result below and rerun the setup step."
            case .queued, .started:
                return "Setup is still running."
            }
        }
        return "Review the current setup result and move into the Steam library."
    }

    private var canInstallDXVK: Bool {
        model.validateDXVKSourceForWizard(dxvkSource).contains(where: { $0.hasPrefix("OK: DXVK payload looks valid") || $0.hasPrefix("OK: DXVK source is a .tar.gz archive") })
    }

    private var requirementsChecklist: some View {
        wizardCard(title: "Requirements Checklist", subtitle: "This keeps the setup understandable for someone who should not have to think in Wine internals.") {
            VStack(alignment: .leading, spacing: 10) {
                checklistRow(title: "Wine", detail: model.detectedWinePathStatus(winePath))
                checklistRow(title: "Winetricks", detail: model.detectedWinetricksStatus())
                checklistRow(title: "DXMT", detail: firstMeaningfulDXMTStatus)
                checklistRow(title: "Bottle", detail: bottleName.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ? "FAIL: Bottle name is empty" : "OK: Bottle name is set to \(bottleName)")
                checklistRow(title: "Steam Setup", detail: model.latestSetupResult == nil ? "PENDING: Run the setup step to install Steam into the managed bottle" : finishSubtitle)
            }
        }
    }

    private var firstMeaningfulDXMTStatus: String {
        let statuses = model.validateDXMTSourceForWizard(dxmtSource)
        if let best = statuses.first(where: { $0.hasPrefix("FAIL:") }) {
            return best
        }
        if let best = statuses.first(where: { $0.contains("payload") || $0.contains(".tar.gz") }) {
            return best
        }
        return statuses.first ?? "FAIL: DXMT source path is empty"
    }

    private var guideBlock: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Getting Started")
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(themeForeground)
            setupBullet("Go to the Steam tab and use Open Steam to sign in and install games.")
            setupBullet("Use Refresh Games after installs so the launcher can discover the new manifests.")
            setupBullet("Use Doctor or Winetricks from Settings if a game needs compatibility help.")
            setupBullet("Keep Steam on the managed bottle unless you have a specific reason to override it.")
        }
        .padding(14)
        .background(themePanelRaised)
        .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
    }

    private func wizardCard<Content: View>(title: String, subtitle: String, @ViewBuilder content: () -> Content) -> some View {
        VStack(alignment: .leading, spacing: 16) {
            VStack(alignment: .leading, spacing: 6) {
                Text(title)
                    .font(.system(size: 26, weight: .bold, design: .rounded))
                    .foregroundStyle(themeForeground)
                Text(subtitle)
                    .foregroundStyle(themeMutedForeground)
                    .fixedSize(horizontal: false, vertical: true)
            }
            content()
        }
        .padding(20)
        .background(themePanel)
        .clipShape(RoundedRectangle(cornerRadius: 22, style: .continuous))
    }

    private func labeledField(_ title: String, text: Binding<String>, browseAction: (() -> Void)?) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title)
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(themeForeground)
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

    private func guidanceBlock(title: String, lines: [String]) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(title)
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(themeForeground)
            ForEach(lines, id: \.self) { line in
                Text(line)
                    .font(.system(.subheadline, design: .monospaced))
                    .foregroundStyle(themeMutedForeground)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
        .padding(14)
        .background(themePanelRaised)
        .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
    }

    private func statusBlock(lines: [String]) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            ForEach(lines, id: \.self) { line in
                Text(line)
                    .font(.system(.subheadline, design: .monospaced))
                    .foregroundStyle(line.hasPrefix("FAIL:") ? Color.red : (line.hasPrefix("WARN:") ? Color.orange : themeForeground))
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
        .padding(14)
        .background(themePanelRaised)
        .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
    }

    private func checklistRow(title: String, detail: String) -> some View {
        HStack(alignment: .top, spacing: 10) {
            Image(systemName: detail.hasPrefix("OK:") ? "checkmark.circle.fill" : (detail.hasPrefix("FAIL:") ? "xmark.circle.fill" : "clock.fill"))
                .foregroundStyle(detail.hasPrefix("OK:") ? themePrimary : (detail.hasPrefix("FAIL:") ? Color.red : Color.orange))
                .padding(.top, 2)
            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(themeForeground)
                Text(detail)
                    .font(.subheadline)
                    .foregroundStyle(themeMutedForeground)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
    }

    private func appCacheURL() -> URL {
        FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Library/Application Support/MySteamWine", isDirectory: true)
            .appendingPathComponent("cache", isDirectory: true)
    }

    private func downloadDXMT() async {
        isDownloadingDXMT = true
        downloadStatusMessage = "Downloading DXMT 0.71..."
        do {
            let cacheURL = appCacheURL().appendingPathComponent("downloads", isDirectory: true)
            try FileManager.default.createDirectory(at: cacheURL, withIntermediateDirectories: true)
            let destinationURL = cacheURL.appendingPathComponent("dxmt-0.71.tar.gz")
            let remoteURL = URL(string: "https://github.com/3Shain/dxmt/releases/download/v0.71/dxmt-windows-and-linux-v0.71.tar.gz")!
            let (temporaryURL, _) = try await URLSession.shared.download(from: remoteURL)
            _ = try? FileManager.default.removeItem(at: destinationURL)
            try FileManager.default.moveItem(at: temporaryURL, to: destinationURL)
            dxmtSource = destinationURL.path
            downloadStatusMessage = "DXMT 0.71 downloaded to \(destinationURL.path)"
        } catch {
            downloadStatusMessage = "Could not download DXMT automatically. You can still point the wizard at a local archive or folder.\n\(error.localizedDescription)"
        }
        isDownloadingDXMT = false
    }

    private func downloadDXVK() async {
        isDownloadingDXMT = true
        downloadStatusMessage = "Downloading DXVK 2.3..."
        do {
            let cacheURL = appCacheURL().appendingPathComponent("downloads", isDirectory: true)
            try FileManager.default.createDirectory(at: cacheURL, withIntermediateDirectories: true)
            let destinationURL = cacheURL.appendingPathComponent("dxvk-2.3.tar.gz")
            let remoteURL = URL(string: "https://github.com/doitsujin/dxvk/releases/download/v2.3/dxvk-2.3.tar.gz")!
            let (temporaryURL, _) = try await URLSession.shared.download(from: remoteURL)
            _ = try? FileManager.default.removeItem(at: destinationURL)
            try FileManager.default.moveItem(at: temporaryURL, to: destinationURL)
            dxvkSource = destinationURL.path
            downloadStatusMessage = "DXVK 2.3 downloaded to \(destinationURL.path)"
        } catch {
            downloadStatusMessage = "Could not download DXVK automatically. You can still point the wizard at a local archive or folder.\n\(error.localizedDescription)"
        }
        isDownloadingDXMT = false
    }

    private func setupBullet(_ text: String) -> some View {
        HStack(alignment: .top, spacing: 10) {
            Image(systemName: "checkmark.circle.fill")
                .foregroundStyle(themePrimary)
                .padding(.top, 1)
            Text(text)
                .foregroundStyle(themeForeground)
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

    private func stepAccent(for step: SetupWizardStep) -> Color {
        switch step {
        case .steam:
            return model.latestSetupResult == nil ? themePanelRaised : themePrimary
        default:
            return themePanelRaised
        }
    }

    private var themeBackground: Color { colorScheme == .dark ? Color(hex: "#20231F") : Color(hex: "#EEF3EC") }
    private var themeSidebar: Color { colorScheme == .dark ? Color(hex: "#181B18") : Color(hex: "#E4ECE3") }
    private var themePanel: Color { colorScheme == .dark ? Color(hex: "#2A302C") : Color(hex: "#F7FBF5") }
    private var themePanelRaised: Color { colorScheme == .dark ? Color(hex: "#353D38") : Color(hex: "#DEE8DE") }
    private var themePrimary: Color { Color(hex: "#6DBB7A") }
    private var themeForeground: Color { colorScheme == .dark ? Color(hex: "#F3F6F2") : Color(hex: "#162019") }
    private var themeMutedForeground: Color { colorScheme == .dark ? Color(hex: "#AEB7AF") : Color(hex: "#55635A") }
}

private struct WinetricksSheet: View {
    @Environment(\.colorScheme) private var colorScheme
    @Bindable var model: AppViewModel

    @State private var verbsText: String = ""
    @State private var interactive: Bool = false
    @FocusState private var isCustomVerbsFocused: Bool

    private let commonPresets: [(label: String, verbs: String)] = [
        ("Core Fonts", "corefonts"),
        ("VC++ 2019", "vcrun2019"),
        ("D3D Compiler 47", "d3dcompiler_47"),
        (".NET 4.8", "dotnet48"),
        ("XACT", "xact"),
        ("DirectPlay", "directplay"),
    ]

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Winetricks")
                        .font(.title2.weight(.bold))
                    Text("Install runtime components into the current bottle or prefix.")
                        .foregroundStyle(.secondary)
                }
                Spacer()
                Button("Close") {
                    model.closeWinetricks()
                }
                .keyboardShortcut(.cancelAction)
            }
            .padding(.horizontal, 24)
            .padding(.top, 20)
            .padding(.bottom, 16)

            Divider()

            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    VStack(alignment: .leading, spacing: 10) {
                        Text("Common Fixes")
                            .font(.headline)
                        LazyVGrid(columns: [GridItem(.adaptive(minimum: 150), spacing: 10)], spacing: 10) {
                            ForEach(commonPresets, id: \.label) { preset in
                                Button(preset.label) {
                                    verbsText = preset.verbs
                                }
                                .buttonStyle(.bordered)
                            }
                        }
                    }

                    VStack(alignment: .leading, spacing: 8) {
                        Text("Verbs")
                            .font(.subheadline.weight(.semibold))
                        Text("Enter one or more Winetricks verbs, separated by commas.")
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                        TextEditor(text: $verbsText)
                            .font(.system(.body, design: .monospaced))
                            .scrollContentBackground(.hidden)
                            .padding(10)
                            .frame(minHeight: 78)
                            .background(editorBackground)
                            .overlay(
                                RoundedRectangle(cornerRadius: 12, style: .continuous)
                                    .stroke(editorBorder, lineWidth: 1)
                            )
                            .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
                            .focused($isCustomVerbsFocused)
                    }

                    Toggle("Run interactively", isOn: $interactive)

                    VStack(alignment: .leading, spacing: 8) {
                        Text("Target")
                            .font(.subheadline.weight(.semibold))
                        Text(model.settingsSummary)
                            .foregroundStyle(.secondary)
                    }

                    VStack(alignment: .leading, spacing: 10) {
                        Text("Detected Components")
                            .font(.headline)
                        ForEach(model.detectedWinetricksComponents()) { component in
                            HStack(alignment: .top, spacing: 12) {
                                Circle()
                                    .fill(componentColor(component.state))
                                    .frame(width: 10, height: 10)
                                    .padding(.top, 4)
                                VStack(alignment: .leading, spacing: 4) {
                                    HStack {
                                        Text(component.title)
                                            .font(.subheadline.weight(.semibold))
                                        Spacer()
                                        Text(componentLabel(component.state))
                                            .font(.caption.weight(.semibold))
                                            .foregroundStyle(componentColor(component.state))
                                    }
                                    Text(component.detail)
                                        .font(.footnote)
                                        .foregroundStyle(.secondary)
                                }
                            }
                            .padding(12)
                            .background(Color.secondary.opacity(0.08))
                            .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
                        }
                    }
                }
                .padding(24)
            }

            Divider()

            HStack {
                Button("Cancel") {
                    model.closeWinetricks()
                }
                .keyboardShortcut(.cancelAction)
                Spacer()
                Button("Run Winetricks") {
                    model.runWinetricks(verbsText: verbsText, interactive: interactive)
                }
                .buttonStyle(.borderedProminent)
                .keyboardShortcut(.defaultAction)
            }
            .padding(24)
            .background(.regularMaterial)
        }
        .frame(width: 620, height: 470)
        .task {
            isCustomVerbsFocused = true
        }
    }

    private var editorBackground: Color {
        colorScheme == .dark ? Color(hex: "#2A302C") : Color(hex: "#F7FBF5")
    }

    private var editorBorder: Color {
        colorScheme == .dark ? Color(hex: "#4A544D") : Color(hex: "#C9D5CA")
    }

    private func componentColor(_ state: WinetricksComponentStatus.State) -> Color {
        switch state {
        case .installed:
            return Color(hex: "#6DBB7A")
        case .missing:
            return Color.secondary
        case .unavailable:
            return Color(hex: "#D96C6C")
        }
    }

    private func componentLabel(_ state: WinetricksComponentStatus.State) -> String {
        switch state {
        case .installed:
            return "Detected"
        case .missing:
            return "Not Found"
        case .unavailable:
            return "Unavailable"
        }
    }
}

private struct SidebarRow: View {
    let runner: RunnerKind
    let isSelected: Bool

    var body: some View {
        HStack(spacing: 10) {
            Image(systemName: runner.symbolName)
                .frame(width: 22)
            Text(runner.rawValue)
            Spacer()
            if !runner.isAvailable {
                Text("Soon")
                    .font(.caption2.weight(.bold))
                    .padding(.horizontal, 7)
                    .padding(.vertical, 4)
                    .background(Color.secondary.opacity(0.14))
                    .clipShape(Capsule())
            }
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 10)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(isSelected ? Color.primary.opacity(0.08) : .clear)
        .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
        .contentShape(Rectangle())
    }
}

private struct GameCard: View {
    @Environment(\.colorScheme) private var colorScheme
    let game: LibraryGame
    let isSelected: Bool
    let isBusy: Bool
    let isDragging: Bool
    let collection: GameCollection
    let onLaunch: () -> Void
    let isPinned: Bool
    let onTogglePin: () -> Void
    let onOpenStore: () -> Void
    let onRevealFiles: () -> Void
    let onOpenDetails: () -> Void
    let onGameSettings: () -> Void
    let onRevealLogs: () -> Void
    let onDebugLaunch: () -> Void
    let onChangeIcon: () -> Void
    let onRemoveFromLibrary: () -> Void

    @State private var isHovered: Bool = false

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            ZStack(alignment: .topLeading) {
                BannerArtwork(
                    url: game.bannerURL,
                    title: game.title,
                    height: 160,
                    installURL: game.installURL,
                    runner: game.runner,
                    appid: game.backendID
                )

                HStack {
                    Menu {
                        Button("Game Details") {
                            onOpenDetails()
                        }
                        Divider()
                        Button(isPinned ? "Unpin from Home" : "Pin to Home") {
                            onTogglePin()
                        }
                        if game.runner == .steam, game.storeURL != nil {
                            Button("Open Steam Store Page") {
                                onOpenStore()
                            }
                        }
                        if game.installURL != nil {
                            Button("Reveal Local Files") {
                                onRevealFiles()
                            }
                        }
                        if game.runner == .steam || game.runner == .wine {
                            Button("Reveal Logs") {
                                onRevealLogs()
                            }
                            Button("Debug Launch") {
                                onDebugLaunch()
                            }
                        }
                        Button("Game Settings") {
                            onGameSettings()
                        }
                        Divider()
                        Button(game.runner == .steam ? "Hide from Library" : "Remove from Library", role: .destructive) {
                            onRemoveFromLibrary()
                        }
                        Button("Change App Icon") {
                            onChangeIcon()
                        }
                    } label: {
                        Image(systemName: "ellipsis")
                            .font(.headline.weight(.bold))
                            .foregroundStyle(.white)
                            .frame(width: 34, height: 34)
                            .background(.black.opacity(0.38))
                            .clipShape(Circle())
                    }
                    .menuStyle(.borderlessButton)
                    .fixedSize()
                    .opacity(isHovered ? 1 : 0)
                    .allowsHitTesting(isHovered)

                    Spacer()
                }
                .padding(10)
            }

            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    HStack(spacing: 8) {
                        Text(game.runner.rawValue)
                            .font(.caption.weight(.semibold))
                            .foregroundStyle(themeMutedForeground)
                        if collection != .none {
                            Pill(
                                text: collection.rawValue,
                                tint: collection.color.opacity(0.18),
                                foreground: collection.color
                            )
                        }
                    }
                    Spacer()
                    Button {
                        onLaunch()
                    } label: {
                        Image(systemName: "play.fill")
                            .font(.subheadline.weight(.bold))
                            .foregroundStyle(Color.black)
                            .frame(width: 36, height: 36)
                            .background(themePrimary)
                            .clipShape(Circle())
                    }
                    .buttonStyle(.plain)
                    .disabled(isBusy || !isHovered)
                    .opacity(isHovered ? (isBusy ? 0.6 : 1) : 0)
                    .allowsHitTesting(isHovered && !isBusy)
                }
                .frame(height: 36)
                if let statsText = game.statsText, !statsText.isEmpty {
                    Text(statsText)
                        .font(.subheadline)
                        .foregroundStyle(themeMutedForeground)
                        .lineLimit(1)
                }
            }
            .padding(14)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(themePanel)
        }
        .clipShape(RoundedRectangle(cornerRadius: 22, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 22, style: .continuous)
                .stroke(isSelected ? themePrimary : themeBorder, lineWidth: isSelected ? 2 : 1)
        )
        .opacity(isDragging ? 0.3 : 1)
        .onHover { hovering in
            isHovered = hovering
        }
    }

    private var themePanel: Color { colorScheme == .dark ? Color(hex: "#2A302C") : Color(hex: "#F7FBF5") }
    private var themeForeground: Color { colorScheme == .dark ? Color(hex: "#D4DBD4") : Color(hex: "#162019") }
    private var themeMutedForeground: Color { colorScheme == .dark ? Color(hex: "#AEB7AF") : Color(hex: "#55635A") }
    private var themePrimary: Color { Color(hex: "#6DBB7A") }
    private var themeBorder: Color { colorScheme == .dark ? Color(hex: "#384139") : Color(hex: "#CCD8CC") }
}

private struct GameDropDelegate: DropDelegate {
    let targetGame: LibraryGame
    @Binding var draggedGame: LibraryGame?
    let model: AppViewModel

    func dropEntered(info: DropInfo) {
        guard let draggedGame, draggedGame.pinID != targetGame.pinID else { return }
        withAnimation(.snappy(duration: 0.14)) {
            model.moveGame(draggedGame, before: targetGame)
        }
    }

    func dropUpdated(info: DropInfo) -> DropProposal? {
        DropProposal(operation: .move)
    }

    func performDrop(info: DropInfo) -> Bool {
        withAnimation(.snappy(duration: 0.1)) {
            draggedGame = nil
        }
        return true
    }
}

private struct BannerArtwork: View {
    @Environment(\.colorScheme) private var colorScheme
    let url: URL?
    let title: String
    let height: CGFloat
    let installURL: URL?
    let runner: RunnerKind
    let appid: String?

    var body: some View {
        ZStack(alignment: .bottomLeading) {
            if let localSteamHeaderImage {
                Image(nsImage: localSteamHeaderImage)
                    .resizable()
                    .interpolation(.high)
                    .scaledToFill()
            } else if let url {
                AsyncImage(url: url) { phase in
                    switch phase {
                    case .empty:
                        placeholder
                    case .success(let image):
                        image
                            .resizable()
                            .scaledToFill()
                    case .failure:
                        placeholder
                    @unknown default:
                        placeholder
                    }
                }
            } else {
                localFallbackArtwork
            }

            Rectangle()
                .fill(.black.opacity(0.18))

            if let steamIcon = steamIconImage {
                Image(nsImage: steamIcon)
                    .resizable()
                    .interpolation(.high)
                    .scaledToFit()
                    .frame(width: 40, height: 40)
                    .padding(14)
                    .shadow(color: .black.opacity(0.3), radius: 10, y: 4)
            }

            Text(title)
                .font(.headline.weight(.bold))
                .foregroundStyle(.white)
                .lineLimit(2)
                .padding(.vertical, 14)
                .padding(.leading, steamIconImage == nil ? 14 : 62)
                .padding(.trailing, 14)
        }
        .frame(maxWidth: .infinity)
        .frame(height: height)
        .clipped()
        .background(themePanel)
        .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
    }

    private var placeholder: some View {
        Rectangle()
            .fill(themePanelRaised)
    }

    private var localFallbackArtwork: some View {
        ZStack(alignment: .bottomTrailing) {
            Rectangle()
                .fill(dominantLocalColor.opacity(0.92))

            if let installURL, let icon = localIconImage(for: installURL) {
                Image(nsImage: icon)
                    .resizable()
                    .interpolation(.high)
                    .scaledToFit()
                    .frame(width: height * 0.42, height: height * 0.42)
                    .padding(14)
                    .shadow(color: .black.opacity(0.28), radius: 10, y: 5)
            } else {
                Image(systemName: runner.symbolName)
                    .font(.system(size: 38, weight: .semibold))
                    .foregroundStyle(.white.opacity(0.92))
                    .padding(18)
            }
        }
    }

    private var dominantLocalColor: Color {
        guard let installURL, let icon = localIconImage(for: installURL) else {
            return themePanelRaised
        }
        return averageColor(for: icon) ?? themePanelRaised
    }

    private func localIconImage(for url: URL) -> NSImage? {
        let image = NSWorkspace.shared.icon(forFile: url.path)
        guard image.size.width > 0, image.size.height > 0 else { return nil }
        return image
    }

    private var steamIconImage: NSImage? {
        guard runner == .steam, let appid, let installURL else { return nil }
        return localSteamIcon(appid: appid, installURL: installURL)
    }

    private var localSteamHeaderImage: NSImage? {
        guard runner == .steam, let appid, let installURL else { return nil }
        return localSteamHeader(appid: appid, installURL: installURL)
    }

    private func localSteamIcon(appid: String, installURL: URL) -> NSImage? {
        let steamRoot = installURL
            .deletingLastPathComponent()
            .deletingLastPathComponent()
        let cacheRoot = steamRoot.appendingPathComponent("appcache/librarycache", isDirectory: true)
        let candidates = [
            cacheRoot.appendingPathComponent("\(appid)_icon.jpg"),
            cacheRoot.appendingPathComponent("\(appid)_icon.png"),
            cacheRoot.appendingPathComponent("\(appid)/icon.jpg"),
            cacheRoot.appendingPathComponent("\(appid)/icon.png"),
        ]

        for candidate in candidates where FileManager.default.fileExists(atPath: candidate.path) {
            if let image = NSImage(contentsOf: candidate) {
                return image
            }
        }
        return nil
    }

    private func localSteamHeader(appid: String, installURL: URL) -> NSImage? {
        let steamRoot = installURL
            .deletingLastPathComponent()
            .deletingLastPathComponent()
        let cacheRoot = steamRoot.appendingPathComponent("appcache/librarycache", isDirectory: true)
        let candidates = [
            cacheRoot.appendingPathComponent("\(appid)_header.jpg"),
            cacheRoot.appendingPathComponent("\(appid)_header.png"),
            cacheRoot.appendingPathComponent("\(appid)_library_600x900.jpg"),
            cacheRoot.appendingPathComponent("\(appid)_library_600x900.png"),
            cacheRoot.appendingPathComponent("\(appid)_library_hero.jpg"),
            cacheRoot.appendingPathComponent("\(appid)_library_hero.png"),
            cacheRoot.appendingPathComponent("\(appid)/header.jpg"),
            cacheRoot.appendingPathComponent("\(appid)/header.png"),
        ]

        for candidate in candidates where FileManager.default.fileExists(atPath: candidate.path) {
            if let image = NSImage(contentsOf: candidate) {
                return image
            }
        }
        return nil
    }

    private func averageColor(for image: NSImage) -> Color? {
        guard
            let tiffData = image.tiffRepresentation,
            let bitmap = NSBitmapImageRep(data: tiffData)
        else {
            return nil
        }

        var red: CGFloat = 0
        var green: CGFloat = 0
        var blue: CGFloat = 0
        var count: CGFloat = 0

        let sampleStep = max(1, min(bitmap.pixelsWide, bitmap.pixelsHigh) / 24)
        for x in stride(from: 0, to: bitmap.pixelsWide, by: sampleStep) {
            for y in stride(from: 0, to: bitmap.pixelsHigh, by: sampleStep) {
                guard let color = bitmap.colorAt(x: x, y: y)?.usingColorSpace(.deviceRGB) else { continue }
                red += color.redComponent
                green += color.greenComponent
                blue += color.blueComponent
                count += 1
            }
        }

        guard count > 0 else { return nil }
        return Color(
            .sRGB,
            red: red / count,
            green: green / count,
            blue: blue / count,
            opacity: 1
        )
    }

    private var themePanel: Color { colorScheme == .dark ? Color(hex: "#2A302C") : Color(hex: "#F7FBF5") }
    private var themePanelRaised: Color { colorScheme == .dark ? Color(hex: "#353D38") : Color(hex: "#DEE8DE") }
}

private struct DragBadge: View {
    let title: String

    var body: some View {
        Text(title)
            .font(.caption.weight(.semibold))
            .foregroundStyle(.white)
            .padding(.horizontal, 10)
            .padding(.vertical, 8)
            .background(.black.opacity(0.75))
            .clipShape(Capsule())
    }
}

private struct GameSettingsSheet: View {
    @Bindable var model: AppViewModel
    let game: LibraryGame

    @State private var launchArguments: String = ""
    @State private var workingDirectoryPath: String = ""
    @State private var environmentText: String = ""
    @State private var graphicsBackend: GraphicsBackendOption = .dxmt
    @State private var launchExecutablePath: String = ""
    @State private var customBannerPath: String = ""
    @State private var collection: GameCollection = .none
    @State private var assignedBottleName: String = ""
    @State private var assignedExternalPrefix: String = ""

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text(game.title)
                        .font(.title2.weight(.bold))
                    Text("Launch preferences")
                        .foregroundStyle(.secondary)
                }
                Spacer()
                Button("Close") {
                    model.closeGameSettings()
                }
                .keyboardShortcut(.cancelAction)
            }
            .padding(.horizontal, 24)
            .padding(.top, 20)
            .padding(.bottom, 16)

            Divider()

            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    settingsSection("Quick Start", subtitle: "Pick how this title should launch without having to think about backend commands.") {
                        labeledField("Extra Launch Arguments", text: $launchArguments)
                        labeledField("Working Folder", text: $workingDirectoryPath, browse: pickDirectory)
                        labeledField("Launch File", text: $launchExecutablePath, browse: pickExecutable)
                    }
                    if game.runner == .steam {
                        Text("If you set a launch executable here, this Steam title will launch through that executable instead of the plain App ID path whenever custom per-game settings are needed.")
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                    }
                    if game.runner == .wine {
                        settingsSection("Game File", subtitle: "Folder-based imports can point at the exact EXE you want to use.") {
                            HStack(spacing: 10) {
                                Button("Choose from Imported Folder") {
                                    if let value = pickExecutableFromInstallFolder() {
                                        launchExecutablePath = value
                                        if workingDirectoryPath.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                                            workingDirectoryPath = URL(fileURLWithPath: value).deletingLastPathComponent().path
                                        }
                                    }
                                }
                                .disabled(!hasDirectoryInstallRoot)

                                if !hasDirectoryInstallRoot {
                                    Text("Import a folder-based game to use this shortcut.")
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                }
                            }
                        }
                    }
                    settingsSection("Appearance", subtitle: "Swap in your own banner art for the library card.") {
                        labeledField("Custom Banner", text: $customBannerPath, browse: pickImage)
                    }
                    settingsSection("Container", subtitle: "Override the default bottle or external prefix for just this title.") {
                        VStack(alignment: .leading, spacing: 8) {
                            Text("Assigned Bottle")
                                .font(.subheadline.weight(.semibold))
                            Picker("Assigned Bottle", selection: $assignedBottleName) {
                                Text("Default").tag("")
                                ForEach(model.managedBottleNames, id: \.self) { name in
                                    Text(name).tag(name)
                                }
                            }
                            .pickerStyle(.menu)
                            .disabled(!assignedExternalPrefix.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                            if !assignedExternalPrefix.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                                Text("Using an external prefix overrides the bottle selection.")
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }
                        }
                        labeledField("Assigned External Prefix", text: $assignedExternalPrefix, browse: pickDirectory)
                        if !assignedBottleName.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                            Button("Clear Bottle Assignment") {
                                assignedBottleName = ""
                            }
                            .buttonStyle(.borderless)
                        }
                        if !assignedExternalPrefix.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                            Button("Clear External Prefix") {
                                assignedExternalPrefix = ""
                            }
                            .buttonStyle(.borderless)
                        }
                    }

                    settingsSection("Rendering", subtitle: "Choose the graphics path this title should prefer.") {
                        Picker("Graphics Backend", selection: $graphicsBackend) {
                            ForEach(GraphicsBackendOption.allCases) { backend in
                                Text(backend.rawValue).tag(backend)
                            }
                        }
                        .pickerStyle(.segmented)

                        let effectiveOverrides = model.effectiveGraphicsOverrides(
                            for: game,
                            graphicsBackend: graphicsBackend,
                            assignedBottleName: assignedBottleName,
                            assignedExternalPrefix: assignedExternalPrefix,
                            environmentText: environmentText
                        )

                        VStack(alignment: .leading, spacing: 10) {
                            Text("Effective Graphics Overrides")
                                .font(.subheadline.weight(.semibold))
                            overrideRow("Target", effectiveOverrides.targetLabel)
                            overrideRow("Prefix", effectiveOverrides.prefixPath, monospaced: true)
                            overrideRow("Backend", effectiveOverrides.graphicsBackend.rawValue)
                            overrideRow(
                                "Registry",
                                effectiveOverrides.registryOverrides.isEmpty
                                    ? "No persistent DLL overrides found in this prefix."
                                    : effectiveOverrides.registryOverrides.joined(separator: "\n"),
                                monospaced: true
                            )
                            overrideRow(
                                "Launch",
                                effectiveOverrides.launchOverrides ?? "No extra launch-time WINEDLLOVERRIDES for this app.",
                                monospaced: true
                            )
                            if !effectiveOverrides.environmentWarnings.isEmpty {
                                overrideRow(
                                    "Custom Env",
                                    effectiveOverrides.environmentWarnings.joined(separator: "\n"),
                                    monospaced: true
                                )
                                Text("These environment variables can override what the launcher would normally apply.")
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }
                        }
                        .padding(12)
                        .background(Color.secondary.opacity(0.08))
                        .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
                    }

                    settingsSection("Library", subtitle: "Use collections to keep testing, favorites, and finished games tidy.") {
                        Picker("Collection", selection: $collection) {
                            ForEach(GameCollection.allCases) { value in
                                Text(value.rawValue).tag(value)
                            }
                        }
                        .pickerStyle(.menu)
                    }

                    settingsSection("Advanced", subtitle: "Optional environment variables for one-off compatibility tweaks.") {
                        VStack(alignment: .leading, spacing: 8) {
                            Text("Environment Variables")
                                .font(.subheadline.weight(.semibold))
                            TextEditor(text: $environmentText)
                                .frame(minHeight: 160)
                                .padding(8)
                                .background(Color.secondary.opacity(0.08))
                                .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
                        }
                    }
                }
                .padding(24)
                .frame(maxWidth: .infinity, alignment: .leading)
            }
            .frame(maxHeight: .infinity)

            Divider()

            HStack {
                Button("Cancel") {
                    model.closeGameSettings()
                }
                .keyboardShortcut(.cancelAction)
                Spacer()
                Button("Save") {
                    model.saveSettings(
                        for: game,
                        launchArguments: launchArguments,
                        workingDirectoryPath: workingDirectoryPath,
                        environmentText: environmentText,
                        graphicsBackend: graphicsBackend,
                        launchExecutablePath: launchExecutablePath,
                        customBannerPath: customBannerPath,
                        collection: collection,
                        assignedBottleName: assignedBottleName,
                        assignedExternalPrefix: assignedExternalPrefix
                    )
                    model.closeGameSettings()
                }
                .buttonStyle(.borderedProminent)
                .keyboardShortcut(.defaultAction)
            }
            .padding(24)
            .background(.regularMaterial)
        }
        .frame(width: 680, height: 640)
        .task {
            let settings = model.settings(for: game)
            launchArguments = settings.launchArguments
            workingDirectoryPath = settings.workingDirectoryPath
            environmentText = settings.environmentText
            graphicsBackend = settings.graphicsBackend
            launchExecutablePath = settings.launchExecutablePath
            customBannerPath = settings.customBannerPath
            collection = settings.collection
            assignedBottleName = settings.assignedBottleName
            assignedExternalPrefix = settings.assignedExternalPrefix
        }
    }

    private func labeledField(_ title: String, text: Binding<String>, browse: (() -> String?)? = nil) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title)
                .font(.subheadline.weight(.semibold))
            HStack(spacing: 10) {
                TextField(title, text: text)
                    .textFieldStyle(.roundedBorder)
                if let browse {
                    Button("Browse") {
                        if let value = browse() {
                            text.wrappedValue = value
                        }
                    }
                }
            }
        }
    }

    private func settingsSection<Content: View>(_ title: String, subtitle: String, @ViewBuilder content: () -> Content) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(title)
                .font(.headline)
            Text(subtitle)
                .font(.footnote)
                .foregroundStyle(.secondary)
            content()
        }
        .padding(16)
        .background(Color.secondary.opacity(0.08))
        .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
    }

    private func overrideRow(_ label: String, _ value: String, monospaced: Bool = false) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(label)
                .font(.caption.weight(.semibold))
                .foregroundStyle(.secondary)
            Text(value)
                .font(monospaced ? .system(.footnote, design: .monospaced) : .subheadline)
                .textSelection(.enabled)
                .frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    private func pickDirectory() -> String? {
        let panel = NSOpenPanel()
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.allowsMultipleSelection = false
        return panel.runModal() == .OK ? panel.url?.path : nil
    }

    private func pickExecutable() -> String? {
        let panel = NSOpenPanel()
        panel.canChooseFiles = true
        panel.canChooseDirectories = false
        panel.allowedContentTypes = [
            UTType(filenameExtension: "exe"),
            UTType(filenameExtension: "bat"),
            UTType(filenameExtension: "cmd"),
            UTType(filenameExtension: "msi"),
        ].compactMap { $0 }
        panel.allowsMultipleSelection = false
        return panel.runModal() == .OK ? panel.url?.path : nil
    }

    private var hasDirectoryInstallRoot: Bool {
        guard let installURL = game.installURL else { return false }
        var isDirectory: ObjCBool = false
        return FileManager.default.fileExists(atPath: installURL.path, isDirectory: &isDirectory) && isDirectory.boolValue
    }

    private func pickExecutableFromInstallFolder() -> String? {
        guard let installURL = game.installURL, hasDirectoryInstallRoot else {
            return pickExecutable()
        }

        let panel = NSOpenPanel()
        panel.directoryURL = installURL
        panel.canChooseFiles = true
        panel.canChooseDirectories = false
        panel.allowedContentTypes = [
            UTType(filenameExtension: "exe"),
            UTType(filenameExtension: "bat"),
            UTType(filenameExtension: "cmd"),
            UTType(filenameExtension: "msi"),
        ].compactMap { $0 }
        panel.allowsMultipleSelection = false
        panel.prompt = "Choose Launch EXE"
        panel.message = "Select the Windows executable this entry should launch."
        return panel.runModal() == .OK ? panel.url?.path : nil
    }

    private func pickImage() -> String? {
        let panel = NSOpenPanel()
        panel.canChooseFiles = true
        panel.canChooseDirectories = false
        panel.allowedContentTypes = [.png, .jpeg, .tiff, .image]
        panel.allowsMultipleSelection = false
        return panel.runModal() == .OK ? panel.url?.path : nil
    }
}

private struct GameDetailsSheet: View {
    @Bindable var model: AppViewModel
    let game: LibraryGame

    var body: some View {
        let settings = model.settings(for: game)

        VStack(spacing: 0) {
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text(game.title)
                        .font(.title2.weight(.bold))
                    Text(game.runner.rawValue)
                        .foregroundStyle(.secondary)
                }
                Spacer()
                Button("Done") {
                    model.closeGameDetails()
                }
                .keyboardShortcut(.cancelAction)
            }
            .padding(.horizontal, 24)
            .padding(.top, 20)
            .padding(.bottom, 14)

            Divider()

            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    sectionHeader("Artwork")
                    BannerArtwork(
                        url: game.bannerURL,
                        title: game.title,
                        height: 220,
                        installURL: game.installURL,
                        runner: game.runner,
                        appid: game.backendID
                    )

                    sectionHeader("Actions")
                    HStack(spacing: 10) {
                        Button(game.status.localizedCaseInsensitiveContains("installer") ? "Run Installer" : "Play") {
                            model.launch(game)
                        }
                        .buttonStyle(.borderedProminent)

                        Button("Debug") {
                            model.debugLaunch(game)
                        }

                        Button("Logs") {
                            model.openLogViewer(for: game)
                        }

                        Button("Settings") {
                            model.openGameSettingsFromDetails(for: game)
                        }
                    }

                    sectionHeader("Details")
                    VStack(alignment: .leading, spacing: 12) {
                        metadataRow("Source", game.runner.rawValue)
                        if let installSize = model.installSizeText(for: game) {
                            metadataRow("Install Size", installSize)
                        }
                        if let playtime = model.playtimeText(for: game) {
                            metadataRow("Playtime", playtime)
                        }
                        if let lastPlayed = model.lastPlayedText(for: game) {
                            metadataRow("Last Played", lastPlayed)
                        }
                        metadataRow("Collection", settings.collection.rawValue)
                        metadataRow("Target", targetSummary(settings))
                        ForEach(model.explicitMetadataRows(for: game), id: \.label) { row in
                            metadataRow(row.label, row.value)
                        }
                    }
                    .textSelection(.enabled)
                    .padding(16)
                    .background(Color.secondary.opacity(0.08))
                    .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))

                    if game.runner == .wine {
                        sectionHeader("Wine Target")
                        VStack(alignment: .leading, spacing: 12) {
                            Text("This entry can use a custom executable, working directory, environment variables, graphics backend, and assigned bottle or prefix.")
                                .font(.subheadline)
                                .foregroundStyle(.secondary)
                            Button("Open Game Settings") {
                                model.openGameSettingsFromDetails(for: game)
                            }
                        }
                        .padding(16)
                        .background(Color.secondary.opacity(0.08))
                        .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
                    }
                }
                .padding(24)
            }
        }
        .frame(width: 760, height: 700)
    }

    private func sectionHeader(_ title: String) -> some View {
        Text(title)
            .font(.headline.weight(.semibold))
    }

    private func metadataRow(_ label: String, _ value: String) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(label)
                .font(.caption.weight(.semibold))
                .foregroundStyle(.secondary)
            Text(value)
                .font(.subheadline)
        }
    }

    private func targetSummary(_ settings: StoredGameSettings) -> String {
        if !settings.assignedExternalPrefix.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            return settings.assignedExternalPrefix
        }
        if !settings.assignedBottleName.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            return settings.assignedBottleName
        }
        return "Default target"
    }
}

private struct LogViewerSheet: View {
    @Bindable var model: AppViewModel

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Text(model.selectedLogTitle)
                    .font(.title3.weight(.bold))
                Spacer()
                if !model.selectedLogEntries.isEmpty {
                    Picker("Log File", selection: $model.selectedLogEntryID) {
                        ForEach(model.selectedLogEntries) { entry in
                            Text(entry.title).tag(Optional(entry.id))
                        }
                    }
                    .pickerStyle(.menu)
                    .frame(width: 220)
                }
                Button("Copy") {
                    let pasteboard = NSPasteboard.general
                    pasteboard.clearContents()
                    pasteboard.setString(model.selectedLogEntry?.text ?? model.selectedLogText, forType: .string)
                }
                Button("Refresh") {
                    model.refreshLogViewer()
                }
                Button("Done") {
                    model.closeLogViewer()
                }
                .keyboardShortcut(.cancelAction)
            }
            .padding(.horizontal, 24)
            .padding(.top, 20)
            .padding(.bottom, 14)

            Divider()

            VStack(spacing: 0) {
                if let highlightedError = highlightedErrorExcerpt {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Likely Error")
                            .font(.headline)
                        Text(highlightedError)
                            .font(.system(.footnote, design: .monospaced))
                            .textSelection(.enabled)
                            .frame(maxWidth: .infinity, alignment: .leading)
                    }
                    .padding(16)
                    .background(Color.secondary.opacity(0.08))
                    .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
                    .padding(.horizontal, 24)
                    .padding(.top, 18)
                }

                ScrollViewReader { proxy in
                    ScrollView([.vertical, .horizontal]) {
                        Text(logText)
                            .font(.system(.footnote, design: .monospaced))
                            .textSelection(.enabled)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding(16)
                            .background(Color.secondary.opacity(0.08))
                            .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
                            .padding(24)
                            .id("log-top")
                    }
                    .onChange(of: model.selectedLogEntryID) { _, _ in
                        withAnimation(.easeOut(duration: 0.12)) {
                            proxy.scrollTo("log-top", anchor: .top)
                        }
                    }
                }
            }
        }
        .frame(width: 860, height: 640)
    }

    private var logText: String {
        model.selectedLogEntry?.text ?? model.selectedLogText
    }

    private var highlightedErrorExcerpt: String? {
        let interestingLines = logText
            .split(whereSeparator: \.isNewline)
            .map(String.init)
            .filter {
                let lowered = $0.lowercased()
                return lowered.contains("err:")
                    || lowered.contains("error")
                    || lowered.contains("exception")
                    || lowered.contains("fatal")
                    || lowered.contains("unhandled")
            }

        guard !interestingLines.isEmpty else { return nil }
        return interestingLines.suffix(8).joined(separator: "\n")
    }
}

private struct EmptyLibraryState: View {
    @Environment(\.colorScheme) private var colorScheme
    let title: String
    let message: String
    let showsActions: Bool
    let isBusy: Bool
    let onOpenSettings: () -> Void
    let onRefresh: () -> Void

    var body: some View {
        VStack(spacing: 16) {
            Image(systemName: "square.stack.3d.up.slash")
                .font(.system(size: 42, weight: .semibold))
                .foregroundStyle(themeMutedForeground)
            Text("No \(title) items yet")
                .font(.title3.weight(.semibold))
                .foregroundStyle(themeForeground)
            Text(message)
                .font(.subheadline)
                .foregroundStyle(themeMutedForeground)
                .multilineTextAlignment(.center)
                .frame(maxWidth: 420)
            if showsActions {
                HStack(spacing: 10) {
                    Button {
                        onOpenSettings()
                    } label: {
                        Label("Open Settings", systemImage: "slider.horizontal.3")
                    }

                    Button {
                        onRefresh()
                    } label: {
                        Label("Run Refresh Again", systemImage: "arrow.clockwise")
                    }
                    .buttonStyle(.borderedProminent)
                }
                .disabled(isBusy)
                .opacity(isBusy ? 0.6 : 1)
            }
        }
        .frame(maxWidth: .infinity, minHeight: 360)
        .padding(24)
        .background(themePanel)
        .clipShape(RoundedRectangle(cornerRadius: 28, style: .continuous))
    }

    private var themePanel: Color { colorScheme == .dark ? Color(hex: "#2A302C") : Color(hex: "#F7FBF5") }
    private var themeForeground: Color { colorScheme == .dark ? Color(hex: "#D4DBD4") : Color(hex: "#162019") }
    private var themeMutedForeground: Color { colorScheme == .dark ? Color(hex: "#AEB7AF") : Color(hex: "#55635A") }
}

private func moduleNSImage(named name: String) -> NSImage? {
    if let bundleURL = Bundle.module.url(forResource: name, withExtension: "png"),
       let image = NSImage(contentsOf: bundleURL) {
        return image
    }

    let sourceURL = URL(fileURLWithPath: #filePath)
    let repoRoot = sourceURL
        .deletingLastPathComponent()
        .deletingLastPathComponent()
        .deletingLastPathComponent()
    let assetURL = repoRoot.appendingPathComponent("assets/\(name).png")
    return NSImage(contentsOf: assetURL)
}

private struct Pill: View {
    let text: String
    let tint: Color
    let foreground: Color

    var body: some View {
        Text(text)
            .font(.caption.weight(.bold))
            .foregroundStyle(foreground)
            .padding(.horizontal, 10)
            .padding(.vertical, 7)
            .background(tint)
            .clipShape(Capsule())
    }
}

private extension HealthStatus {
    var color: Color {
        switch self {
        case .unknown:
            return Color.secondary.opacity(0.28)
        case .healthy:
            return Color(hex: "#64B86A")
        case .warning:
            return Color.secondary.opacity(0.38)
        case .error:
            return Color(hex: "#E46A5A")
        }
    }

    var showsIndicator: Bool {
        self == .error
    }

    var showsIssueBadge: Bool {
        self == .error
    }
}

private extension GameCollection {
    var color: Color {
        switch self {
        case .none:
            return Color.secondary
        case .favorites:
            return Color(hex: "#E6C15A")
        case .finished:
            return Color(hex: "#64B86A")
        case .testing:
            return Color(hex: "#59A8E0")
        case .broken:
            return Color(hex: "#E46A5A")
        }
    }
}

private extension Color {
    init(hex: String) {
        let hex = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)
        var int: UInt64 = 0
        Scanner(string: hex).scanHexInt64(&int)
        let a, r, g, b: UInt64
        switch hex.count {
        case 3:
            (a, r, g, b) = (255, (int >> 8) * 17, (int >> 4 & 0xF) * 17, (int & 0xF) * 17)
        case 6:
            (a, r, g, b) = (255, int >> 16, int >> 8 & 0xFF, int & 0xFF)
        case 8:
            (a, r, g, b) = (int >> 24, int >> 16 & 0xFF, int >> 8 & 0xFF, int & 0xFF)
        default:
            (a, r, g, b) = (255, 0, 0, 0)
        }

        self.init(
            .sRGB,
            red: Double(r) / 255,
            green: Double(g) / 255,
            blue: Double(b) / 255,
            opacity: Double(a) / 255
        )
    }
}
