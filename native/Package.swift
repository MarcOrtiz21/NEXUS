// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "NEXUS",
    platforms: [
        .macOS(.v14)
    ],
    targets: [
        .executableTarget(
            name: "NEXUS",
            path: "Sources/NEXUS"
        )
    ]
)
