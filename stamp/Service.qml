import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import qs.Commons
import qs.Ui

Item {
  id: root

  property var shell: null
  property var stamp: JSON.parse(Quickshell.env("OMALAB_STAMP") || "{}")
  signal remapRequested()
  readonly property string mark: [
    " ▄████▄  ▄██▄██▄  ▄████▄  ██      ▄████▄  █████▄ ",
    " ██  ██  ██ █ ██  ██  ██  ██      ██  ██  ██  ██ ",
    " ██  ██  ██ █ ██  ██████  ██      ██████  █████▄ ",
    " ██  ██  ██   ██  ██  ██  ██      ██  ██  ██  ██ ",
    " ▀████▀  ██   ██  ██  ██  ██████  ██  ██  █████▀ "
  ].join("\n")

  IpcHandler {
    target: "omalab.stamp"

    function geometry(size: string, scale: real): bool {
      root.stamp = Object.assign({}, root.stamp, {size: size, scale: scale})
      root.remapRequested()
      return true
    }
  }

  Variants {
    model: Quickshell.screens

    PanelWindow {
      id: panel
      required property var modelData
      screen: modelData
      visible: !!root.stamp.plugin && !remapGuard.remapping
      anchors { bottom: true; right: true }
      margins { bottom: 32; right: 32 }
      implicitWidth: Math.min(340, screen.width - 64)
      implicitHeight: facts.implicitHeight
      color: "transparent"
      mask: Region {}
      exclusionMode: ExclusionMode.Ignore
      WlrLayershell.namespace: "omalab-stamp"
      WlrLayershell.layer: WlrLayer.Background
      WlrLayershell.keyboardFocus: WlrKeyboardFocus.None

      ScreenMoveRemap {
        id: remapGuard
        window: panel
      }

      Connections {
        target: root
        function onRemapRequested() { remapGuard.remapping = true }
      }

      Column {
        id: facts
        width: parent.width
        spacing: 7
        opacity: 0.42

        Text {
          width: parent.width
          text: root.mark
          color: Color.accent
          font.family: "monospace"
          font.pixelSize: 9
          lineHeightMode: Text.FixedHeight
          lineHeight: 9
          horizontalAlignment: Text.AlignRight
          renderType: Text.NativeRendering
        }

        Rectangle {
          width: parent.width
          height: 1
          color: Color.accent
        }

        Text {
          width: parent.width
          text: String(root.stamp.plugin || "") + "  /  " + String(root.stamp.commit || "unversioned") + (root.stamp.dirty ? "+dirty" : "")
          color: Color.accent
          font.family: "monospace"
          font.pixelSize: 11
          elide: Text.ElideMiddle
          horizontalAlignment: Text.AlignRight
          renderType: Text.NativeRendering
        }

        Text {
          width: parent.width
          text: String(root.stamp.theme || "") + "  /  " + String(root.stamp.size || "") + "@" + String(root.stamp.scale || 1)
          color: Color.accent
          font.family: "monospace"
          font.pixelSize: 11
          elide: Text.ElideRight
          horizontalAlignment: Text.AlignRight
          renderType: Text.NativeRendering
        }

        Text {
          width: parent.width
          text: "LAB ONLY  /  " + String(root.stamp.date || "")
          color: Color.accent
          font.family: "monospace"
          font.pixelSize: 9
          horizontalAlignment: Text.AlignRight
          renderType: Text.NativeRendering
        }
      }
    }
  }
}
