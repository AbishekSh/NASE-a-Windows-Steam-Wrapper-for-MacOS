import AppKit
import SwiftUI
import UniformTypeIdentifiers

struct EmptyLibraryState: View {
    @Environment(\.colorScheme) private var colorScheme
    let title: String
    let message: String
    let showsActions: Bool
    let isBusy: Bool
    let isLoading: Bool
    let onOpenSettings: () -> Void
    let onRefresh: () -> Void

    var body: some View {
        VStack(spacing: 16) {
            if isLoading {
                ProgressView()
                    .controlSize(.large)
            } else {
                Image(systemName: "square.stack.3d.up.slash")
                    .font(.system(size: 42, weight: .semibold))
                    .foregroundStyle(themeMutedForeground)
            }
            Text(isLoading ? "Refreshing \(title) library" : "No \(title) items yet")
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

func moduleNSImage(named name: String) -> NSImage? {
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

struct Pill: View {
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

extension HealthStatus {
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

extension GameCollection {
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

extension Color {
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
