// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "NEXUS",
    defaultLocalization: "es",
    platforms: [
        .macOS(.v14)
    ],
    targets: [
        .executableTarget(
            name: "NEXUS",
            path: "Sources/NEXUS",
            resources: [
                .process("Resources"),
            ]
        )
    ]
)
