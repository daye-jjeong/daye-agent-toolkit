// swift-tools-version: 6.0

import PackageDescription

let package = Package(
    name: "BackgroundAutomator",
    platforms: [
        .macOS(.v14),
    ],
    products: [
        .library(
            name: "BackgroundAutomatorCore",
            targets: ["BackgroundAutomatorCore"]
        ),
        .library(
            name: "BackgroundAutomatorRuntime",
            targets: ["BackgroundAutomatorRuntime"]
        ),
        .executable(
            name: "BackgroundAutomatorProbe",
            targets: ["BackgroundAutomatorProbe"]
        ),
        .executable(
            name: "BackgroundAutomatorApp",
            targets: ["BackgroundAutomatorApp"]
        ),
    ],
    targets: [
        .target(
            name: "BackgroundAutomatorCore"
        ),
        .target(
            name: "BackgroundAutomatorRuntime",
            dependencies: ["BackgroundAutomatorCore"],
            resources: [
                .process("Resources"),
            ]
        ),
        .executableTarget(
            name: "BackgroundAutomatorProbe",
            dependencies: ["BackgroundAutomatorRuntime"]
        ),
        .executableTarget(
            name: "BackgroundAutomatorApp",
            dependencies: ["BackgroundAutomatorRuntime"]
        ),
        .testTarget(
            name: "BackgroundAutomatorCoreTests",
            dependencies: ["BackgroundAutomatorCore"]
        ),
        .testTarget(
            name: "BackgroundAutomatorRuntimeTests",
            dependencies: ["BackgroundAutomatorRuntime"],
            path: "Tests",
            exclude: [
                "BackgroundAutomatorCoreTests",
            ],
            sources: [
                "BackgroundAutomatorRuntimeTests",
            ],
            resources: [
                .copy("Fixtures"),
            ]
        ),
    ]
)
