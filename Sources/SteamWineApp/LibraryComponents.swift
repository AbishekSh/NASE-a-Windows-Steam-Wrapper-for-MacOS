import AppKit
import SwiftUI
import UniformTypeIdentifiers

struct SidebarRow: View {
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

struct GameCard: View {
    @Environment(\.colorScheme) private var colorScheme
    let game: LibraryGame
    let isBusy: Bool
    let isDragging: Bool
    let collection: GameCollection
    let launchStatus: GameLaunchStatus?
    let canStop: Bool
    let steamCacheURL: URL?
    let onLaunch: () -> Void
    let onStop: () -> Void
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
    let onUpdateSourceGame: () -> Void
    let onVerifySourceGame: () -> Void
    let onRepairSourceGame: () -> Void
    let onUninstallSourceGame: () -> Void

    @State private var isHovered: Bool = false

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            ZStack(alignment: .topLeading) {
                BannerArtwork(
                    url: game.bannerURL,
                    title: game.title,
                    height: 128,
                    installURL: game.installURL,
                    runner: game.runner,
                    appid: game.backendID,
                    steamCacheURL: steamCacheURL
                )
            }

            VStack(alignment: .leading, spacing: 10) {
                HStack(alignment: .firstTextBaseline, spacing: 10) {
                    Text(game.title)
                        .font(.headline.weight(.semibold))
                        .foregroundStyle(themeForeground)
                        .lineLimit(1)
                    Spacer(minLength: 8)
                    cardActionMenu
                    Button {
                        if canStop {
                            onStop()
                        } else {
                            onLaunch()
                        }
                    } label: {
                        Image(systemName: canStop ? "stop.fill" : ([.epic, .gog].contains(game.runner) && game.installURL == nil ? "arrow.down" : "play.fill"))
                            .font(.subheadline.weight(.bold))
                            .foregroundStyle(Color.black)
                            .frame(width: 34, height: 34)
                            .background(canStop ? Color(hex: "#D96C6C") : themePrimary)
                            .clipShape(Circle())
                    }
                    .buttonStyle(.plain)
                    .opacity(isBusy ? 0.55 : 1)
                    .disabled(launchStatus?.phase == .launching)
                    .help(canStop ? "Stop \(game.title)" : ([.epic, .gog].contains(game.runner) && game.installURL == nil ? "Install \(game.title)" : "Play \(game.title)"))
                }
                .frame(height: 36)

                HStack(spacing: 8) {
                    HStack(spacing: 7) {
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
                        if let launchStatus {
                            Pill(
                                text: launchStatus.phase.rawValue,
                                tint: launchTint(for: launchStatus.phase),
                                foreground: launchForeground(for: launchStatus.phase)
                            )
                        }
                    }
                    Spacer()
                    if let statsText = game.statsText, !statsText.isEmpty {
                        Text(statsText)
                            .font(.caption)
                            .foregroundStyle(themeMutedForeground)
                            .lineLimit(1)
                    }
                }
                .frame(height: 26)
            }
            .padding(12)
            .frame(maxWidth: .infinity, minHeight: 96, alignment: .leading)
            .background(themePanel)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(themePanel)
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .stroke(themeBorder, lineWidth: 1)
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

    private func launchTint(for phase: GameLaunchPhase) -> Color {
        switch phase {
        case .launching:
            return Color(hex: "#D9B650").opacity(0.18)
        case .running:
            return Color(hex: "#6DBB7A").opacity(0.18)
        case .exited:
            return Color.secondary.opacity(0.14)
        case .failed:
            return Color(hex: "#D96C6C").opacity(0.18)
        }
    }

    private func launchForeground(for phase: GameLaunchPhase) -> Color {
        switch phase {
        case .launching:
            return Color(hex: "#D9B650")
        case .running:
            return Color(hex: "#6DBB7A")
        case .exited:
            return themeMutedForeground
        case .failed:
            return Color(hex: "#D96C6C")
        }
    }

    private var cardActionMenu: some View {
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
            if [.epic, .gog].contains(game.runner), game.installURL != nil {
                Divider()
                Button("Update") { onUpdateSourceGame() }
                Button("Verify Files") { onVerifySourceGame() }
                Button("Repair and Update") { onRepairSourceGame() }
                Button("Uninstall", role: .destructive) { onUninstallSourceGame() }
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
            CardActionMenuLabel(isHovered: isHovered)
        }
        .menuStyle(.borderlessButton)
        .menuIndicator(.hidden)
        .fixedSize()
    }
}

struct CardActionMenuLabel: View {
    @Environment(\.colorScheme) private var colorScheme
    let isHovered: Bool

    var body: some View {
        Image(systemName: "ellipsis")
            .font(.system(size: 17, weight: .bold))
            .symbolRenderingMode(.monochrome)
            .foregroundStyle(foregroundColor)
            .frame(width: 36, height: 32)
        .background(background)
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .stroke(borderColor, lineWidth: 1)
        )
        .shadow(color: .black.opacity(isHovered ? 0.22 : 0.12), radius: isHovered ? 8 : 4, y: 2)
        .accessibilityLabel("Game actions")
    }

    private var background: some ShapeStyle {
        colorScheme == .dark
            ? AnyShapeStyle(Color(hex: "#26302B").opacity(0.86))
            : AnyShapeStyle(Color.white.opacity(0.88))
    }

    private var foregroundColor: Color {
        colorScheme == .dark ? Color(hex: "#DDE6DD") : Color(hex: "#162019")
    }

    private var borderColor: Color {
        colorScheme == .dark ? Color.white.opacity(0.14) : Color.black.opacity(0.12)
    }
}

struct GameDropDelegate: DropDelegate {
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

struct BannerArtwork: View {
    @Environment(\.colorScheme) private var colorScheme
    let url: URL?
    let title: String
    let height: CGFloat
    let installURL: URL?
    let runner: RunnerKind
    let appid: String?
    let steamCacheURL: URL?

    var body: some View {
        ZStack(alignment: .bottomLeading) {
            if let customImage {
                artworkLayer(Image(nsImage: customImage))
            } else if let localSteamBannerImage {
                artworkLayer(Image(nsImage: localSteamBannerImage))
            } else if let url {
                AsyncImage(url: url) { phase in
                    switch phase {
                    case .empty:
                        placeholder
                    case .success(let image):
                        artworkLayer(image)
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

            LinearGradient(
                colors: [
                    .black.opacity(0.55),
                    .black.opacity(0.26),
                    .clear,
                ],
                startPoint: .bottomLeading,
                endPoint: .topTrailing
            )

            if let steamLogoImage {
                Image(nsImage: steamLogoImage)
                    .resizable()
                    .interpolation(.high)
                    .scaledToFit()
                    .frame(maxWidth: min(320, height * 2.7), maxHeight: height * 0.58, alignment: .leading)
                    .shadow(color: .black.opacity(0.48), radius: 7, y: 3)
                    .padding(.leading, steamIconImage == nil ? 16 : 80)
                    .padding(.trailing, 16)
                    .padding(.bottom, 14)
                    .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .bottomLeading)
            } else {
                Text(title)
                    .font(.system(size: 22, weight: .heavy, design: .rounded))
                    .foregroundStyle(.white)
                    .lineLimit(2)
                    .minimumScaleFactor(0.72)
                    .shadow(color: .black.opacity(0.55), radius: 7, y: 3)
                    .padding(.leading, steamIconImage == nil ? 16 : 80)
                    .padding(.trailing, 16)
                    .padding(.bottom, 14)
                    .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .bottomLeading)
            }

            if let steamIcon = steamIconImage {
                Image(nsImage: steamIcon)
                    .resizable()
                    .interpolation(.high)
                    .scaledToFit()
                    .frame(width: 42, height: 42)
                    .padding(8)
                    .background(.black.opacity(0.28))
                    .clipShape(RoundedRectangle(cornerRadius: 7, style: .continuous))
                    .overlay(
                        RoundedRectangle(cornerRadius: 7, style: .continuous)
                            .stroke(.white.opacity(0.16), lineWidth: 1)
                    )
                    .padding(14)
                    .shadow(color: .black.opacity(0.28), radius: 8, y: 3)
            }
        }
        .frame(maxWidth: .infinity)
        .frame(height: height)
        .clipped()
        .background(themePanel)
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
    }

    private var placeholder: some View {
        Rectangle()
            .fill(themePanelRaised)
    }

    private func artworkLayer(_ image: Image) -> some View {
        ZStack {
            image
                .resizable()
                .interpolation(.high)
                .scaledToFill()
                .frame(maxWidth: .infinity, maxHeight: height)
        }
        .frame(maxWidth: .infinity, maxHeight: height)
        .clipped()
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

    private var localSteamBannerImage: NSImage? {
        guard runner == .steam, let appid else { return nil }
        return localSteamBanner(appid: appid)
    }

    private var steamIconImage: NSImage? {
        guard runner == .steam, let appid else { return nil }
        return localSteamIcon(appid: appid)
    }

    private var steamLogoImage: NSImage? {
        guard runner == .steam, let appid else { return nil }
        return localSteamLogo(appid: appid)
    }

    private var customImage: NSImage? {
        guard let url, url.isFileURL else { return nil }
        return NSImage(contentsOf: url)
    }

    private func localSteamBanner(appid: String) -> NSImage? {
        guard let cacheRoot = steamCacheURL else { return nil }
        let candidates = [
            cacheRoot.appendingPathComponent("\(appid)_library_hero.jpg"),
            cacheRoot.appendingPathComponent("\(appid)_library_hero.png"),
            cacheRoot.appendingPathComponent("\(appid)/library_hero.jpg"),
            cacheRoot.appendingPathComponent("\(appid)/library_hero.png"),
            cacheRoot.appendingPathComponent("\(appid)_header.jpg"),
            cacheRoot.appendingPathComponent("\(appid)_header.png"),
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

    private func localSteamIcon(appid: String) -> NSImage? {
        guard let cacheRoot = steamCacheURL else { return nil }
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

    private func localSteamLogo(appid: String) -> NSImage? {
        guard let cacheRoot = steamCacheURL else { return nil }
        let directCandidates = [
            cacheRoot.appendingPathComponent("\(appid)_logo.png"),
            cacheRoot.appendingPathComponent("\(appid)/logo.png"),
        ]

        for candidate in directCandidates where FileManager.default.fileExists(atPath: candidate.path) {
            if let image = NSImage(contentsOf: candidate) {
                return image
            }
        }

        let appFolder = cacheRoot.appendingPathComponent(appid, isDirectory: true)
        guard let nestedCandidates = try? FileManager.default.contentsOfDirectory(
            at: appFolder,
            includingPropertiesForKeys: nil,
            options: [.skipsHiddenFiles]
        ) else {
            return nil
        }

        for folder in nestedCandidates where folder.hasDirectoryPath {
            let candidate = folder.appendingPathComponent("logo.png")
            if FileManager.default.fileExists(atPath: candidate.path), let image = NSImage(contentsOf: candidate) {
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
