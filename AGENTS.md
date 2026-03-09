Project: SteamWineWrapper

Goal:
Create a macOS application that runs Windows Steam via Wine.

Architecture:
runtime manager
bottle manager
dependency installer
game launcher
advisor system

Wine prefix location:
~/Library/Application Support/MySteamWine

Graphics stack:
Wine + Vulkan + MoltenVK + DXVK

Dependencies:
Wine
Winetricks
DXVK
Steam