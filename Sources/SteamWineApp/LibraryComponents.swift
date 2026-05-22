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
    let steamCacheURL: URL?
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
                    appid: game.backendID,
                    steamCacheURL: steamCacheURL
                )
            }

            VStack(alignment: .leading, spacing: 7) {
                Text(game.title)
                    .font(.headline.weight(.semibold))
                    .foregroundStyle(themeForeground)
                    .lineLimit(1)

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
                    cardActionMenu
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
                    .opacity(isBusy ? 0.55 : 1)
                }
                .frame(height: 32)
                if let statsText = game.statsText, !statsText.isEmpty {
                    Text(statsText)
                        .font(.caption)
                        .foregroundStyle(themeMutedForeground)
                        .lineLimit(1)
                }
            }
            .padding(12)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(themePanel)
        }
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
            } else if let localSteamHeaderImage {
                artworkLayer(Image(nsImage: localSteamHeaderImage))
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

            if let steamIcon = steamIconImage {
                Image(nsImage: steamIcon)
                    .resizable()
                    .interpolation(.high)
                    .scaledToFit()
                    .frame(width: 40, height: 40)
                    .padding(14)
                    .shadow(color: .black.opacity(0.3), radius: 10, y: 4)
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
                .blur(radius: 10)
                .saturation(0.9)
                .opacity(0.68)
                .clipped()

            Rectangle()
                .fill(.black.opacity(colorScheme == .dark ? 0.16 : 0.08))

            image
                .resizable()
                .interpolation(.high)
                .scaledToFit()
                .padding(.horizontal, 8)
                .padding(.vertical, 6)
                .shadow(color: .black.opacity(0.22), radius: 8, y: 3)
        }
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
        guard runner == .steam, let appid else { return nil }
        return localSteamIcon(appid: appid)
    }

    private var localSteamHeaderImage: NSImage? {
        guard runner == .steam, let appid else { return nil }
        return localSteamHeader(appid: appid)
    }

    private var customImage: NSImage? {
        guard let url, url.isFileURL else { return nil }
        return NSImage(contentsOf: url)
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

    private func localSteamHeader(appid: String) -> NSImage? {
        guard let cacheRoot = steamCacheURL else { return nil }
        let candidates = [
            cacheRoot.appendingPathComponent("\(appid)_header.jpg"),
            cacheRoot.appendingPathComponent("\(appid)_header.png"),
            cacheRoot.appendingPathComponent("\(appid)_library_600x900.jpg"),
            cacheRoot.appendingPathComponent("\(appid)_library_600x900.png"),
            cacheRoot.appendingPathComponent("\(appid)_library_hero.jpg"),
            cacheRoot.appendingPathComponent("\(appid)_library_hero.png"),
            cacheRoot.appendingPathComponent("\(appid)/header.jpg"),
            cacheRoot.appendingPathComponent("\(appid)/header.png"),
            cacheRoot.appendingPathComponent("\(appid)/library_hero.jpg"),
            cacheRoot.appendingPathComponent("\(appid)/library_hero.png"),
            cacheRoot.appendingPathComponent("\(appid)/library_600x900.jpg"),
            cacheRoot.appendingPathComponent("\(appid)/library_600x900.png"),
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
