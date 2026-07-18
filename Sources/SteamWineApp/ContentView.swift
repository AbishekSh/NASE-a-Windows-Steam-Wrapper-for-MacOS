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
        .sheet(isPresented: $model.isShowingSetupWizard) {
            SetupWizardSheet(model: model)
                .interactiveDismissDisabled()
        }
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

            if shouldShowSidebarFooter {
                Divider()

                VStack(spacing: 8) {
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
                            sidebarFooterLabel("Open Steam", systemImage: "play.circle")
                        }
                        .buttonStyle(.plain)

                        Button {
                            model.refreshGames()
                        } label: {
                            sidebarFooterLabel("Refresh", systemImage: "arrow.clockwise")
                        }
                        .buttonStyle(.plain)
                    }

                    if model.selectedRunner == .epic {
                        Button {
                            model.refreshEpicLibrary()
                        } label: {
                            sidebarFooterLabel("Refresh Epic", systemImage: "arrow.clockwise")
                        }
                        .buttonStyle(.plain)
                    }

                    addGameControl
                }
                .padding(10)
                .background(themePanel)
            }
        }
        .background(themeSidebar)
        .navigationTitle("Sources")
    }

    private var library: some View {
        VStack(spacing: 0) {
            VStack(alignment: .leading, spacing: 12) {
                ViewThatFits(in: .horizontal) {
                    HStack(alignment: .center, spacing: 12) {
                        libraryTitleBlock
                        Spacer(minLength: 12)
                        primaryActionControls
                    }

                    VStack(alignment: .leading, spacing: 10) {
                        libraryTitleBlock
                        primaryActionControls
                    }
                }

                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 8) {
                        HStack(spacing: 8) {
                            Image(systemName: "magnifyingglass")
                                .foregroundStyle(.secondary)
                            TextField("Search library", text: $model.searchText)
                                .textFieldStyle(.plain)
                        }
                        .padding(.horizontal, 12)
                        .frame(minWidth: 180, idealWidth: 260, maxWidth: 320)
                        .frame(height: 34)
                        .background(themeControlBackground)
                        .clipShape(RoundedRectangle(cornerRadius: 7, style: .continuous))
                        .overlay(
                            RoundedRectangle(cornerRadius: 7, style: .continuous)
                                .stroke(themeControlBorder, lineWidth: 1)
                        )

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
                        .fixedSize()

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
                        .fixedSize()

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
                            .fixedSize()
                        }

                        Spacer(minLength: 0)
                    }
                }
                .scrollClipDisabled()
            }
            .padding(.horizontal, 20)
            .padding(.vertical, 14)
            .background(themeToolbar)

            GeometryReader { geometry in
                ScrollView {
                    if model.filteredGames.isEmpty {
                        EmptyLibraryState(
                            title: model.selectedRunner?.rawValue ?? "Library",
                            message: model.libraryEmptyMessage,
                            showsActions: model.shouldShowSteamEmptyStateActions,
                            isBusy: model.isBusy,
                            isLoading: model.isRefreshingSteamGames,
                            onOpenSettings: {
                                model.openSettings()
                            },
                            onRefresh: {
                                model.refreshGames()
                            }
                        )
                        .padding(20)
                    } else {
                        LazyVGrid(columns: gridColumns(for: geometry.size.width), spacing: 24) {
                            ForEach(model.filteredGames) { game in
                                GameCard(
                                    game: game,
                                    isBusy: model.isBusy,
                                    isDragging: draggedGame?.pinID == game.pinID,
                                    collection: model.settings(for: game).collection,
                                    launchStatus: model.launchStatus(for: game),
                                    canStop: model.canStop(game),
                                    steamCacheURL: model.steamLibraryCacheURL,
                                    onLaunch: {
                                        model.launch(game)
                                    },
                                    onStop: {
                                        model.stop(game)
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
    private var themeControlBackground: Color { colorScheme == .dark ? Color(hex: "#20251F") : Color(hex: "#F4F8F2") }
    private var themeControlBorder: Color { colorScheme == .dark ? Color.white.opacity(0.07) : Color.black.opacity(0.08) }

    private func gridColumns(for availableWidth: CGFloat) -> [GridItem] {
        let spacing: CGFloat = 28
        let minimumCardWidth: CGFloat = availableWidth < 760 ? 320 : 420
        return [
            GridItem(.adaptive(minimum: minimumCardWidth, maximum: 620), spacing: spacing)
        ]
    }

    private var libraryTitleBlock: some View {
        VStack(alignment: .leading, spacing: 3) {
            Text(model.selectedRunner?.rawValue ?? "Library")
                .font(.system(size: 22, weight: .bold, design: .rounded))
            Text(model.settingsSummary)
                .font(.caption)
                .foregroundStyle(.secondary)
                .lineLimit(1)
        }
    }

    private var primaryActionControls: some View {
        HStack(spacing: 10) {
            Button {
                model.openSettings()
            } label: {
                toolbarButtonLabel("Settings", systemImage: "slider.horizontal.3")
            }
            .buttonStyle(.plain)
        }
    }

    private var shouldShowSidebarFooter: Bool {
        model.selectedRunner == .steam || model.selectedRunner == .epic || model.shouldShowAddButton
    }

    @ViewBuilder
    private var addGameControl: some View {
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
                    sidebarFooterLabel("Add", systemImage: "plus")
                }
                .menuStyle(.borderlessButton)
            } else {
                Button {
                    model.performPrimaryAddAction()
                } label: {
                    sidebarFooterLabel(model.selectedRunnerActionTitle, systemImage: "plus")
                }
                .buttonStyle(.plain)
            }
        }
    }

    @ViewBuilder
    private func sidebarFooterLabel(_ title: String, systemImage: String) -> some View {
        Label(title, systemImage: systemImage)
            .font(.system(size: 13, weight: .semibold))
            .foregroundStyle(colorScheme == .dark ? Color(hex: "#E6ECE6") : Color(hex: "#162019"))
            .lineLimit(1)
            .minimumScaleFactor(0.9)
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(.horizontal, 12)
            .frame(height: 34)
            .background(themeControlBackground)
            .clipShape(RoundedRectangle(cornerRadius: 7, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: 7, style: .continuous)
                    .stroke(themeControlBorder, lineWidth: 1)
            )
    }

    @ViewBuilder
    private func toolbarButtonLabel(_ title: String, systemImage: String) -> some View {
        Label(title, systemImage: systemImage)
            .font(.system(size: 14, weight: .semibold))
            .foregroundStyle(colorScheme == .dark ? Color(hex: "#E6ECE6") : Color(hex: "#162019"))
            .lineLimit(1)
            .minimumScaleFactor(0.9)
            .padding(.horizontal, 12)
            .frame(height: 34)
            .background(themeControlBackground)
            .clipShape(RoundedRectangle(cornerRadius: 7, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: 7, style: .continuous)
                    .stroke(themeControlBorder, lineWidth: 1)
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
        .background(themeControlBackground)
        .clipShape(RoundedRectangle(cornerRadius: 7, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 7, style: .continuous)
                .stroke(themeControlBorder, lineWidth: 1)
        )
    }
}
