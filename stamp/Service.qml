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
  // Bitmap rows describe the mark, not font glyphs. Merge each horizontal run
  // so cells never overlap or depend on fallback-font bearings and line height.
  readonly property var markRows: [
    ".#####. ##...## ..###.. ##..... ..###.. ######.",
    "##...## ###.### .##.##. ##..... .##.##. ##...##",
    "##...## ####### ##...## ##..... ##...## ##...##",
    "##...## ##.#.## ####### ##..... ####### ######.",
    "##...## ##...## ##...## ##..... ##...## ##...##",
    "##...## ##...## ##...## ##..... ##...## ##...##",
    ".#####. ##...## ##...## ####### ##...## ######."
  ]
  readonly property var markRuns: {
    const runs = []
    for (let row = 0; row < markRows.length; row++) {
      const pixels = markRows[row]
      for (let column = 0; column < pixels.length;) {
        if (pixels[column] !== "#") { column++; continue }
        const start = column
        while (column < pixels.length && pixels[column] === "#") column++
        runs.push({row: row, column: start, span: column - start})
      }
    }
    return runs
  }

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

        Item {
          id: wordmark
          width: parent.width
          readonly property real pixelRatio: Screen.devicePixelRatio || 1
          readonly property real cellSize: Math.floor(Math.min(6, width / root.markRows[0].length) * pixelRatio) / pixelRatio
          readonly property real leftInset: Math.round((width - root.markRows[0].length * cellSize) * pixelRatio) / pixelRatio
          height: root.markRows.length * cellSize

          Repeater {
            model: root.markRuns

            Rectangle {
              required property var modelData
              x: wordmark.leftInset + modelData.column * wordmark.cellSize
              y: modelData.row * wordmark.cellSize
              width: modelData.span * wordmark.cellSize
              height: wordmark.cellSize
              color: Color.accent
              antialiasing: false
            }
          }
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
          renderType: Text.QtRendering
        }

        Text {
          width: parent.width
          text: String(root.stamp.theme || "") + "  /  " + String(root.stamp.size || "") + "@" + String(root.stamp.scale || 1)
          color: Color.accent
          font.family: "monospace"
          font.pixelSize: 11
          elide: Text.ElideRight
          horizontalAlignment: Text.AlignRight
          renderType: Text.QtRendering
        }

        Text {
          width: parent.width
          text: "LAB ONLY  /  " + String(root.stamp.date || "")
          color: Color.accent
          font.family: "monospace"
          font.pixelSize: 9
          horizontalAlignment: Text.AlignRight
          renderType: Text.QtRendering
        }
      }
    }
  }
}
