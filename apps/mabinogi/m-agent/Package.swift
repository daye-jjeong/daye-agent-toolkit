// swift-tools-version: 6.0

import PackageDescription

let package = Package(
    name: "MAgent",
    platforms: [
        .macOS(.v14),
    ],
    products: [
        .library(
            name: "MAgentCore",
            targets: ["MAgentCore"]
        ),
        .library(
            name: "MAgentRuntime",
            targets: ["MAgentRuntime"]
        ),
        .executable(
            name: "MAgentProbe",
            targets: ["MAgentProbe"]
        ),
        .executable(
            name: "MAgentApp",
            targets: ["MAgentApp"]
        ),
    ],
    targets: [
        .target(
            name: "MAgentCore"
        ),
        .target(
            name: "MAgentRuntime",
            dependencies: ["MAgentCore"],
            resources: [
                .process("Resources"),
            ]
        ),
        .executableTarget(
            name: "MAgentProbe",
            dependencies: ["MAgentRuntime"]
        ),
        .executableTarget(
            name: "MAgentApp",
            dependencies: [
                "MAgentCore",
                "MAgentRuntime",
            ]
        ),
        .testTarget(
            name: "MAgentCoreTests",
            dependencies: ["MAgentCore"]
        ),
        .testTarget(
            name: "MAgentRuntimeTests",
            dependencies: ["MAgentRuntime"],
            path: "Tests",
            exclude: [
                "MAgentCoreTests",
            ],
            sources: [
                "MAgentRuntimeTests",
            ],
            resources: [
                .copy("Fixtures"),
            ]
        ),
    ]
)
