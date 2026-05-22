// swift-tools-version: 5.10
import PackageDescription

let package = Package(
    name: "SteamWineApp",
    platforms: [
        .macOS(.v14),
    ],
    products: [
        .executable(name: "SteamWineApp", targets: ["SteamWineApp"]),
    ],
    targets: [
        .executableTarget(
            name: "SteamWineApp",
            path: "Sources/SteamWineApp",
            resources: [
                .process("Resources"),
            ]
        ),
    ]
)
