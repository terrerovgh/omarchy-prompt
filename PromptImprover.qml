import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import QtQuick
import qs.Commons
import qs.Commons as Commons
import qs.Ui

// Overlay card that rewrites the selected prompt for a chosen LLM, following
// that vendor's official prompting guide (guides/*.md), and keeps a history.
// Summoned by bin/omarchy-prompt-selection with {"text": "..."} or
// {"view": "history"}. All work happens in promptctl.py; this file is UI only.
// Every displayed string is untrusted, so all text renders as PlainText.
Item {
  id: root

  property string omarchyPath: Quickshell.env("OMARCHY_PATH")
  property var shell: null
  property var manifest: null

  readonly property string pluginId: (manifest && manifest.id) || "io.github.terrerovgh.prompt-improver"
  readonly property string ctlPath: String(Qt.resolvedUrl("promptctl.py")).replace(/^file:\/\//, "")
  readonly property int maxChars: 20000

  property bool opened: false
  property string view: "improve"           // improve | history

  // Catalog (from `promptctl.py models`)
  property var families: []
  property var categories: []
  property string family: ""
  property string version: ""
  property string context: "auto"
  property var engines: []                  // installed CLIs + ready API profiles
  property string backend: "auto"
  property string resolvedBackend: ""

  // Improve view
  property string phase: "idle"             // idle | loading | done | error | empty
  property string stage: ""
  property string original: ""
  property string english: ""
  property string sourceLang: ""
  property string improved: ""
  property var changes: []
  property var ctx: ({})
  property int entryId: -1
  property bool favorite: false
  property string errorText: ""
  property var pendingRequest: null         // a run waiting for the current one to stop

  // History view
  property var historyItems: []
  property string filterText: ""
  property string historyCategory: ""
  property string historyFamily: ""
  property int selectedIndex: 0
  property int confirmDeleteId: -1
  property var actionQueue: []

  property string fontFamily: Style.font.menuFamily
  property color background: Commons.Color.menu.background
  property color foreground: Commons.Color.menu.text
  property color accent: Commons.Color.menu.selectedText
  property color border: Commons.Color.menu.border
  property color selectedBackground: Commons.Color.menu.selectedBackground
  property color selectedText: Commons.Color.menu.selectedText
  property var borderSpec: Border.surfaceSpec("menu", "border", border, Math.max(1, Style.space(2)))
  property color scrim: Commons.Color.menu.scrim
  readonly property int cornerRadius: Style.cornerRadius
  property int contentMargin: Style.spacing.panelPadding
  property int gap: Style.spacing.rowGap
  property int rowHeight: Math.max(Style.space(50), Style.font.body + Style.font.caption + Style.spacing.rowPaddingX * 2)

  Commons.Translations { id: strings; directory: Qt.resolvedUrl("i18n") }

  // ------------------------------------------------------------ helpers

  function ctl(args) { return ["python3", "-I", root.ctlPath].concat(args) }

  function catLabel(c) { return c ? strings.t("cat." + c, c) : "" }

  function familyById(id) {
    for (var i = 0; i < root.families.length; i++) if (root.families[i].id === id) return root.families[i]
    return null
  }

  function versionLabel(famId, verId) {
    var f = root.familyById(famId)
    if (!f) return verId
    for (var i = 0; i < f.versions.length; i++) if (f.versions[i].id === verId) return f.versions[i].label
    return verId
  }

  readonly property var familyOptions: root.families.map(function(f) { return { value: f.id, label: f.label } })
  readonly property var versionOptions: {
    var f = root.familyById(root.family)
    return f ? f.versions.map(function(v) { return { value: v.id, label: v.label } }) : []
  }
  readonly property var contextOptions: [{ value: "auto", label: strings.t("auto") }].concat(
    root.categories.map(function(c) { return { value: c, label: root.catLabel(c) } }))
  function engineLabel(id, short) {
    for (var i = 0; i < root.engines.length; i++)
      if (root.engines[i].id === id) return short ? (root.engines[i].short || root.engines[i].label) : root.engines[i].label
    return id
  }
  readonly property var engineOptions: [{
      value: "auto",
      label: root.resolvedBackend ? strings.t("autoEngine").arg(root.engineLabel(root.resolvedBackend, true)) : strings.t("auto")
    }].concat(root.engines.filter(function(e) { return !e.blocked }).map(function(e) { return { value: e.id, label: e.label } }))
  readonly property var historyCategoryOptions: [{ value: "", label: strings.t("all") }].concat(
    root.categories.map(function(c) { return { value: c, label: root.catLabel(c) } }))
  readonly property var historyFamilyOptions: [{ value: "", label: strings.t("all") }].concat(root.familyOptions)

  function setTarget(target) {
    if (typeof target !== "string" || target.indexOf("/") < 0) return
    var parts = target.split("/")
    var f = root.familyById(parts[0])
    if (!f && root.families.length > 0) return
    root.family = parts[0]
    root.version = parts.slice(1).join("/")
  }

  // ---------------------------------------------------------- lifecycle

  function open(payloadJson) {
    var payload = ({})
    try { payload = JSON.parse(payloadJson || "{}") } catch (e) { payload = ({}) }
    // Refresh the catalog and the installed-engine list (cached by promptctl).
    if (!modelsProcess.running) modelsProcess.running = true

    root.opened = true
    Qt.callLater(function() { keyCatcher.forceActiveFocus() })

    if (payload.view === "history") {
      root.setView("history")
      return
    }
    root.view = "improve"
    // The launcher sends {"source": "selection"}: promptctl reads the selection
    // itself through wl-paste, so the text never sits in a process argument.
    var fromSelection = payload.source === "selection"
    var text = typeof payload.text === "string" ? payload.text.trim().slice(0, root.maxChars) : ""
    if (!fromSelection && !text) {
      // Opened without a selection: keep the last result if there is one.
      if (root.phase === "done" || root.phase === "loading") return
      root.original = ""
      root.improved = ""
      root.phase = "empty"
      return
    }
    root.original = text
    root.english = ""
    root.sourceLang = ""
    root.runImprove(false, fromSelection)
  }

  function close() { root.opened = false }

  function dismiss() {
    root.opened = false
    root.confirmDeleteId = -1
    if (root.shell && typeof root.shell.hide === "function") root.shell.hide(root.pluginId)
  }

  function toggle() {
    if (root.opened) root.dismiss()
    else root.open("{}")
  }

  function setView(v) {
    root.view = v
    root.confirmDeleteId = -1
    if (v === "history") root.refreshHistory()
    Qt.callLater(function() { keyCatcher.forceActiveFocus() })
  }

  // ------------------------------------------------------------ improve

  // The request (with the text) goes to promptctl on stdin, never in argv.
  function runImprove(reuseEnglish, fromSelection) {
    if (!root.original && !fromSelection) return
    var req = { ui_lang: strings.language || "en" }
    if (fromSelection) req.source = "selection"
    else req.text = root.original
    if (root.family && root.version) req.target = root.family + "/" + root.version
    if (root.context !== "auto") req.context = root.context
    if (root.backend) req.backend = root.backend
    if (reuseEnglish && root.sourceLang) {
      req.source_lang = root.sourceLang
      req.english = root.english || root.original
    }

    root.phase = "loading"
    root.stage = reuseEnglish && root.sourceLang
      ? strings.t("rewriting").arg(root.versionLabel(root.family, root.version))
      : strings.t("translating")
    root.improved = ""
    root.changes = []
    root.ctx = ({})
    root.entryId = -1
    root.favorite = false
    root.errorText = ""
    flick.contentY = 0

    if (improveProcess.running) {
      // Stop the outdated run; onExited starts this one.
      root.pendingRequest = req
      improveProcess.running = false
      return
    }
    root.launch(req)
  }

  function launch(req) {
    improveProcess.request = req
    improveProcess.running = true
  }

  function handleLine(line) {
    if (root.pendingRequest !== null) return
    var msg = null
    try { msg = JSON.parse(String(line || "").trim()) } catch (e) { return }
    if (!msg || typeof msg !== "object") return

    if (typeof msg.stage === "string") {
      if (msg.stage === "input") root.original = typeof msg.text === "string" ? msg.text.slice(0, root.maxChars) : ""
      else if (msg.stage === "translating") root.stage = strings.t("translating")
      else if (msg.stage === "translated") {
        root.sourceLang = String(msg.source || "").slice(0, 16)
        root.english = typeof msg.english === "string" ? msg.english : ""
      } else if (msg.stage === "retrying") {
        root.stage = strings.t("retrying")
      } else if (msg.stage === "rewriting") {
        root.stage = strings.t("rewriting").arg(String(msg.target || "").slice(0, 60))
          + "\n" + root.engineLabel(String(msg.backend || ""))
      }
      return
    }
    if (msg.ok === true && typeof msg.improved === "string") {
      root.improved = msg.improved
      root.changes = Array.isArray(msg.changes) ? msg.changes.filter(function(c) { return typeof c === "string" }) : []
      root.ctx = msg.context && typeof msg.context === "object" ? msg.context : ({})
      root.entryId = typeof msg.id === "number" ? msg.id : -1
      if (typeof msg.source === "string" && msg.source) root.sourceLang = msg.source.slice(0, 16)
      root.setTarget(msg.target)
      root.phase = "done"
    } else if (msg.ok === false) {
      root.errorText = typeof msg.error === "string" ? msg.error.slice(0, 300) : "?"
      root.phase = root.errorText === "empty text" ? "empty" : "error"
    }
  }

  function copyText(text) {
    if (!text) return
    // Through promptctl's stdin to wl-copy's stdin: never a process argument.
    copyProcess.request = { text: text }
    if (!copyProcess.running) copyProcess.running = true
    root.dismiss()
  }

  function toggleFavorite() {
    if (root.entryId < 0) return
    root.favorite = !root.favorite
    root.queueAction(["history", "fav", String(root.entryId)])
  }

  // ------------------------------------------------------------ history

  function refreshHistory() {
    var args = ["history", "list", "--limit", "300"]
    if (root.filterText.trim()) args = args.concat(["--q", root.filterText.trim()])
    if (root.historyCategory) args = args.concat(["--category", root.historyCategory])
    if (root.historyFamily) args = args.concat(["--family", root.historyFamily])
    if (historyProcess.running) { historyRefresh.restart(); return }
    historyProcess.command = root.ctl(args)
    historyProcess.running = true
  }

  function setFilter(text) {
    root.filterText = text.slice(0, 120)
    root.selectedIndex = 0
    historyRefresh.restart()
  }

  readonly property var selectedItem: root.selectedIndex >= 0 && root.selectedIndex < root.historyItems.length
    ? root.historyItems[root.selectedIndex] : null
  onSelectedItemChanged: previewFlick.contentY = 0

  function selectRelative(delta) {
    if (root.historyItems.length === 0) return
    root.selectedIndex = Math.max(0, Math.min(root.historyItems.length - 1, root.selectedIndex + delta))
    historyList.positionViewAtIndex(root.selectedIndex, ListView.Contain)
    root.confirmDeleteId = -1
  }

  function openSelected() {
    var item = root.selectedItem
    if (!item) return
    getProcess.command = root.ctl(["history", "get", String(item.id)])
    getProcess.running = true
  }

  function loadEntry(item) {
    if (improveProcess.running) { root.pendingRequest = null; improveProcess.running = false }
    root.original = String(item.original || "")
    root.english = String(item.english || "")
    root.sourceLang = String(item.source_lang || "")
    root.improved = String(item.improved || "")
    root.changes = Array.isArray(item.changes) ? item.changes : []
    root.ctx = { category: item.category, subtype: item.subtype, title: item.title, tags: item.tags || [] }
    root.entryId = typeof item.id === "number" ? item.id : -1
    root.favorite = !!item.favorite
    root.setTarget(String(item.family) + "/" + String(item.version))
    root.phase = "done"
    root.setView("improve")
  }

  function deleteSelected() {
    var item = root.selectedItem
    if (!item) return
    if (root.confirmDeleteId !== item.id) { root.confirmDeleteId = item.id; return }
    root.confirmDeleteId = -1
    if (item.id === root.entryId) root.entryId = -1
    root.queueAction(["history", "delete", String(item.id)])
  }

  function favoriteSelected() {
    var item = root.selectedItem
    if (!item) return
    if (item.id === root.entryId) root.favorite = !item.favorite
    root.queueAction(["history", "fav", String(item.id)])
  }

  function queueAction(args) {
    root.actionQueue = root.actionQueue.concat([args])
    if (!actionProcess.running) root.nextAction()
  }

  function nextAction() {
    if (root.actionQueue.length === 0) {
      if (root.view === "history") root.refreshHistory()
      return
    }
    var args = root.actionQueue[0]
    root.actionQueue = root.actionQueue.slice(1)
    actionProcess.command = root.ctl(args)
    actionProcess.running = true
  }

  function formatDate(iso) {
    var d = new Date(iso)
    return isNaN(d.getTime()) ? "" : Qt.formatDateTime(d, "d MMM yyyy · HH:mm")
  }

  // ---------------------------------------------------------- processes

  Process {
    id: modelsProcess
    command: root.ctl(["models"])
    running: false
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        var data = null
        try { data = JSON.parse(String(text || "").trim()) } catch (e) { data = null }
        if (!data || !Array.isArray(data.families)) return
        root.families = data.families
        root.categories = Array.isArray(data.categories) ? data.categories : []
        root.engines = Array.isArray(data.engines) ? data.engines : []
        root.resolvedBackend = String(data.resolved_backend || "")
        var b = String(data.backend || "auto")
        if (b !== "auto" && root.engines.filter(function(e) { return e.id === b && !e.blocked }).length === 0) b = "auto"
        if (!improveProcess.running) root.backend = b
        if (!root.family) root.setTarget(String(data.last_target || data["default"] || ""))
        if (!root.familyById(root.family) && root.families.length > 0) {
          root.family = root.families[0].id
          root.version = root.families[0].versions[0].id
        }
      }
    }
  }

  Process {
    id: improveProcess
    property var request: null
    command: root.ctl(["improve", "--stdin"])
    running: false
    stdinEnabled: true
    onStarted: {
      write(JSON.stringify(request || {}) + "\n")
      request = null
    }
    stdout: SplitParser { onRead: data => root.handleLine(data) }
    stderr: StdioCollector {
      waitForEnd: true
      onStreamFinished: if (text.trim() !== "") console.warn(root.pluginId, text.trim().slice(0, 500))
    }
    onExited: function(exitCode, exitStatus) {
      if (root.pendingRequest !== null) {
        var next = root.pendingRequest
        root.pendingRequest = null
        root.launch(next)
        return
      }
      if (root.phase === "loading") {
        root.errorText = "exit " + exitCode
        root.phase = "error"
      }
    }
  }

  Process {
    id: copyProcess
    property var request: null
    command: root.ctl(["copy"])
    running: false
    stdinEnabled: true
    onStarted: {
      write(JSON.stringify(request || {}) + "\n")
      request = null
    }
    onExited: function(exitCode, exitStatus) {
      if (exitCode === 0)
        Quickshell.execDetached([root.omarchyPath + "/bin/omarchy-notification-send", "-t", "2000", strings.t("copied")])
    }
  }

  Process {
    id: historyProcess
    running: false
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        var data = null
        try { data = JSON.parse(String(text || "").trim()) } catch (e) { data = null }
        root.historyItems = data && Array.isArray(data.items) ? data.items : []
        root.selectedIndex = Math.max(0, Math.min(root.selectedIndex, root.historyItems.length - 1))
      }
    }
  }

  Process {
    id: getProcess
    running: false
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        var data = null
        try { data = JSON.parse(String(text || "").trim()) } catch (e) { data = null }
        if (data && data.ok && data.item) root.loadEntry(data.item)
      }
    }
  }

  Process {
    id: actionProcess
    running: false
    onExited: root.nextAction()
  }

  Timer {
    id: historyRefresh
    interval: 150
    onTriggered: root.refreshHistory()
  }

  Component.onCompleted: modelsProcess.running = true

  // ---------------------------------------------------------------- UI

  OverlayWindow {
    id: panel
    shown: root.opened
    WlrLayershell.namespace: "omarchy-prompt-improver"

    Rectangle { anchors.fill: parent; color: root.scrim }

    MouseArea { anchors.fill: parent; onClicked: root.dismiss() }

    BorderSurface {
      id: card
      width: Math.min(Style.space(860), panel.width - Style.gapsOut * 2)
      height: Math.min(Style.space(660), panel.height - Style.gapsOut * 2)
      radius: root.cornerRadius
      anchors.centerIn: parent
      color: root.background
      borderSpec: root.borderSpec
      padding: root.contentMargin

      MouseArea { anchors.fill: parent; onClicked: keyCatcher.forceActiveFocus() }

      // Parent of every control, so keys a control leaves unaccepted land here.
      Item {
        id: keyCatcher
        x: card.contentLeftInset
        y: card.contentTopInset
        width: card.width - card.contentLeftInset - card.contentRightInset
        height: card.height - card.contentTopInset - card.contentBottomInset
        focus: true
        activeFocusOnTab: true

        Keys.onPressed: function(event) {
          var ctrl = (event.modifiers & Qt.ControlModifier) !== 0
          var plain = (event.modifiers & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier)) === 0
          if (event.key === Qt.Key_Escape || (ctrl && event.key === Qt.Key_W)) {
            root.dismiss()
          } else if (ctrl && event.key === Qt.Key_H) {
            root.setView(root.view === "history" ? "improve" : "history")
          } else if (ctrl && event.key === Qt.Key_1) {
            root.setView("improve")
          } else if (ctrl && event.key === Qt.Key_2) {
            root.setView("history")
          } else if (root.view === "improve") {
            if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter || (ctrl && event.key === Qt.Key_C)) {
              if (root.phase === "done") root.copyText(root.improved)
            } else if (ctrl && event.key === Qt.Key_R) {
              root.runImprove(true)
            } else if (ctrl && event.key === Qt.Key_F) {
              root.toggleFavorite()
            } else if (event.key === Qt.Key_Down || (plain && event.key === Qt.Key_J)) {
              flick.scrollBy(Style.space(40))
            } else if (event.key === Qt.Key_Up || (plain && event.key === Qt.Key_K)) {
              flick.scrollBy(-Style.space(40))
            } else if (event.key === Qt.Key_PageDown) {
              flick.scrollBy(flick.height * 0.9)
            } else if (event.key === Qt.Key_PageUp) {
              flick.scrollBy(-flick.height * 0.9)
            } else {
              return
            }
          } else {
            if (event.key !== Qt.Key_Delete) root.confirmDeleteId = -1
            if (event.key === Qt.Key_Down) root.selectRelative(1)
            else if (event.key === Qt.Key_Up) root.selectRelative(-1)
            else if (event.key === Qt.Key_PageDown) root.selectRelative(6)
            else if (event.key === Qt.Key_PageUp) root.selectRelative(-6)
            else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter || (ctrl && event.key === Qt.Key_C)) {
              if (root.selectedItem) root.copyText(String(root.selectedItem.improved || ""))
            } else if (ctrl && event.key === Qt.Key_O) root.openSelected()
            else if (ctrl && event.key === Qt.Key_F) root.favoriteSelected()
            else if (event.key === Qt.Key_Delete) root.deleteSelected()
            else if (ctrl && event.key === Qt.Key_U) root.setFilter("")
            else if (event.key === Qt.Key_Backspace) root.setFilter(root.filterText.slice(0, -1))
            else if (plain && event.text && event.text.length === 1 && event.text.charCodeAt(0) >= 32 && event.text.charCodeAt(0) !== 127)
              root.setFilter(root.filterText + event.text)
            else return
          }
          event.accepted = true
        }

        // Header: title + tabs
        Item {
          id: header
          anchors.top: parent.top
          anchors.left: parent.left
          anchors.right: parent.right
          height: Math.max(titleText.implicitHeight, tabs.implicitHeight)

          Text {
            id: titleText
            textFormat: Text.PlainText
            anchors.left: parent.left
            anchors.right: tabs.left
            anchors.rightMargin: root.gap
            anchors.verticalCenter: parent.verticalCenter
            text: {
              var t = strings.t("title")
              if (root.view === "improve" && root.sourceLang && root.sourceLang !== "en" && root.sourceLang !== "?")
                t += " · " + root.sourceLang.toUpperCase() + " → EN"
              return t
            }
            color: root.accent
            font.family: root.fontFamily
            font.pixelSize: Style.font.bodySmall
            font.bold: true
            elide: Text.ElideRight
          }

          ButtonGroup {
            id: tabs
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            focusable: false
            foreground: root.foreground
            background: root.background
            fontFamily: root.fontFamily
            fontSize: Style.font.caption
            value: root.view
            options: [
              { value: "improve", label: strings.t("tabImprove") },
              { value: "history", label: strings.t("tabHistory") }
            ]
            onChanged: function(v) { root.setView(v) }
          }
        }

        Text {
          id: hint
          textFormat: Text.PlainText
          anchors.bottom: parent.bottom
          anchors.left: parent.left
          anchors.right: parent.right
          text: root.view === "history" ? strings.t("historyHint") : strings.t("hint")
          color: root.foreground
          opacity: 0.4
          font.family: root.fontFamily
          font.pixelSize: Style.font.caption
          horizontalAlignment: Text.AlignRight
          elide: Text.ElideLeft
        }

        // ------------------------------------------------ improve view
        Item {
          id: improveView
          visible: root.view === "improve"
          anchors.top: header.bottom
          anchors.topMargin: root.gap
          anchors.left: parent.left
          anchors.right: parent.right
          anchors.bottom: hint.top
          anchors.bottomMargin: root.gap

          Column {
            id: info
            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right
            spacing: root.gap

            Row {
              id: selectors
              width: parent.width
              spacing: root.gap
              readonly property real cellWidth: (width - spacing * 3) / 4

              Dropdown {
                width: selectors.cellWidth
                label: strings.t("family")
                value: root.family
                options: root.familyOptions
                fontFamily: root.fontFamily
                onChanged: function(v) {
                  if (v === root.family) return
                  root.family = v
                  var f = root.familyById(v)
                  root.version = f && f.versions.length > 0 ? f.versions[0].id : ""
                  root.runImprove(true)
                }
              }
              Dropdown {
                width: selectors.cellWidth
                label: strings.t("version")
                value: root.version
                options: root.versionOptions
                fontFamily: root.fontFamily
                onChanged: function(v) {
                  if (v === root.version) return
                  root.version = v
                  root.runImprove(true)
                }
              }
              Dropdown {
                width: selectors.cellWidth
                label: strings.t("context")
                value: root.context
                options: root.contextOptions
                fontFamily: root.fontFamily
                onChanged: function(v) {
                  if (v === root.context) return
                  root.context = v
                  root.runImprove(true)
                }
              }
              Dropdown {
                width: selectors.cellWidth
                label: strings.t("engine")
                value: root.backend
                options: root.engineOptions
                fontFamily: root.fontFamily
                onChanged: function(v) {
                  if (v === root.backend) return
                  root.backend = v
                  root.runImprove(true)
                }
              }
            }

            Text {
              textFormat: Text.PlainText
              visible: root.original !== ""
              width: parent.width
              text: root.original
              color: root.foreground
              opacity: 0.55
              font.family: root.fontFamily
              font.pixelSize: Style.font.body
              wrapMode: Text.Wrap
              maximumLineCount: 2
              elide: Text.ElideRight
            }

            Text {
              textFormat: Text.PlainText
              visible: root.english !== "" && root.sourceLang !== "en"
              width: parent.width
              text: "EN · " + root.english
              color: root.foreground
              opacity: 0.4
              font.family: root.fontFamily
              font.pixelSize: Style.font.caption
              wrapMode: Text.Wrap
              maximumLineCount: 2
              elide: Text.ElideRight
            }

            Rectangle {
              width: parent.width
              height: Math.max(1, Style.spacing.hairline)
              color: root.foreground
              opacity: 0.15
            }

            Text {
              textFormat: Text.PlainText
              visible: root.phase === "done"
              width: parent.width
              text: {
                var parts = []
                if (root.favorite) parts.push(strings.t("favorite"))
                if (root.ctx.category) parts.push(root.catLabel(root.ctx.category))
                if (root.ctx.subtype) parts.push(root.ctx.subtype)
                var line = parts.join(" · ")
                var tags = Array.isArray(root.ctx.tags) ? root.ctx.tags : []
                if (tags.length > 0) line += "   " + tags.map(function(t) { return "#" + t }).join(" ")
                return line
              }
              color: root.accent
              font.family: root.fontFamily
              font.pixelSize: Style.font.caption
              font.bold: true
              elide: Text.ElideRight
            }
          }

          Flickable {
            id: flick
            anchors.top: info.bottom
            anchors.topMargin: root.gap
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            contentWidth: width
            contentHeight: resultColumn.implicitHeight
            clip: true
            boundsBehavior: Flickable.StopAtBounds

            function scrollBy(delta) {
              contentY = Math.max(0, Math.min(Math.max(0, contentHeight - height), contentY + delta))
            }

            Column {
              id: resultColumn
              width: flick.width
              spacing: root.gap

              TextEdit {
                id: body
                width: parent.width
                readOnly: true
                selectByMouse: true
                activeFocusOnPress: false
                textFormat: TextEdit.PlainText
                wrapMode: TextEdit.Wrap
                text: {
                  if (root.phase === "done") return root.improved
                  if (root.phase === "loading") return root.stage
                  if (root.phase === "empty") return strings.t("empty")
                  if (root.phase === "error") return strings.t("error").arg(root.errorText)
                  return ""
                }
                color: root.foreground
                selectionColor: root.selectedBackground
                selectedTextColor: root.selectedText
                opacity: root.phase === "done" ? 1 : 0.6
                font.family: root.fontFamily
                font.pixelSize: Style.font.body
              }

              Text {
                textFormat: Text.PlainText
                visible: root.phase === "done" && /\[[^\]\n]{2,60}\]/.test(root.improved)
                width: parent.width
                text: strings.t("placeholderNote")
                color: root.accent
                opacity: 0.8
                font.family: root.fontFamily
                font.pixelSize: Style.font.caption
                wrapMode: Text.Wrap
              }

              Text {
                textFormat: Text.PlainText
                visible: root.phase === "done" && root.changes.length > 0
                width: parent.width
                text: strings.t("changes")
                color: root.foreground
                opacity: 0.6
                font.family: root.fontFamily
                font.pixelSize: Style.font.caption
                font.bold: true
              }

              Repeater {
                model: root.phase === "done" ? root.changes : []
                delegate: Text {
                  required property var modelData
                  textFormat: Text.PlainText
                  width: resultColumn.width
                  text: "• " + String(modelData)
                  color: root.foreground
                  opacity: 0.6
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.caption
                  wrapMode: Text.Wrap
                }
              }
            }
          }
        }

        // ------------------------------------------------ history view
        Item {
          id: historyView
          visible: root.view === "history"
          anchors.top: header.bottom
          anchors.topMargin: root.gap
          anchors.left: parent.left
          anchors.right: parent.right
          anchors.bottom: hint.top
          anchors.bottomMargin: root.gap

          Row {
            id: historyBar
            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right
            spacing: root.gap
            height: Math.max(searchText.implicitHeight, Style.spacing.controlHeight)
            readonly property real filterWidth: Math.min(Style.space(190), width / 4)

            Text {
              id: searchText
              textFormat: Text.PlainText
              width: historyBar.width - historyBar.filterWidth * 2 - historyBar.spacing * 2
              anchors.verticalCenter: parent.verticalCenter
              text: root.filterText || strings.t("search")
              color: root.foreground
              opacity: root.filterText ? 1 : 0.5
              font.family: root.fontFamily
              font.pixelSize: Style.font.heading
              elide: Text.ElideRight
            }
            Dropdown {
              width: historyBar.filterWidth
              anchors.verticalCenter: parent.verticalCenter
              showLabel: false
              value: root.historyCategory
              options: root.historyCategoryOptions
              fontFamily: root.fontFamily
              onChanged: function(v) { root.historyCategory = v; root.selectedIndex = 0; root.refreshHistory() }
            }
            Dropdown {
              width: historyBar.filterWidth
              anchors.verticalCenter: parent.verticalCenter
              showLabel: false
              value: root.historyFamily
              options: root.historyFamilyOptions
              fontFamily: root.fontFamily
              onChanged: function(v) { root.historyFamily = v; root.selectedIndex = 0; root.refreshHistory() }
            }
          }

          Text {
            textFormat: Text.PlainText
            visible: root.historyItems.length === 0
            anchors.top: historyBar.bottom
            anchors.topMargin: root.gap * 2
            anchors.horizontalCenter: parent.horizontalCenter
            text: (root.filterText || root.historyCategory || root.historyFamily) ? strings.t("noMatches") : strings.t("noHistory")
            color: root.foreground
            opacity: 0.5
            font.family: root.fontFamily
            font.pixelSize: Style.font.body
          }

          Row {
            visible: root.historyItems.length > 0
            anchors.top: historyBar.bottom
            anchors.topMargin: root.gap
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom

            ListView {
              id: historyList
              width: parent.width * 0.44
              height: parent.height
              clip: true
              spacing: Style.space(4)
              boundsBehavior: Flickable.StopAtBounds
              model: root.historyItems

              delegate: Rectangle {
                id: row
                required property var modelData
                required property int index
                readonly property bool current: index === root.selectedIndex
                width: ListView.view.width - Style.space(8)
                height: root.rowHeight
                radius: root.cornerRadius
                color: current ? root.selectedBackground : "transparent"

                Column {
                  anchors.fill: parent
                  anchors.leftMargin: Style.space(10)
                  anchors.rightMargin: Style.space(10)
                  anchors.topMargin: Style.space(6)
                  anchors.bottomMargin: Style.space(6)
                  spacing: Style.space(2)

                  Text {
                    textFormat: Text.PlainText
                    width: parent.width
                    text: (row.modelData.favorite ? "★ " : "")
                      + (root.confirmDeleteId === row.modelData.id ? "⌫ " : "")
                      + String(row.modelData.title || row.modelData.improved || "").replace(/\s+/g, " ")
                    color: row.current ? root.selectedText : root.foreground
                    font.family: root.fontFamily
                    font.pixelSize: Style.font.body
                    font.bold: true
                    elide: Text.ElideRight
                  }
                  Text {
                    textFormat: Text.PlainText
                    width: parent.width
                    text: root.catLabel(row.modelData.category) + " · " + String(row.modelData.target_label || row.modelData.family)
                      + " · " + root.formatDate(row.modelData.created)
                    color: row.current ? root.selectedText : root.foreground
                    opacity: 0.6
                    font.family: root.fontFamily
                    font.pixelSize: Style.font.caption
                    elide: Text.ElideRight
                  }
                }

                MouseArea {
                  anchors.fill: parent
                  cursorShape: Qt.PointingHandCursor
                  onClicked: { root.selectedIndex = row.index; root.confirmDeleteId = -1; keyCatcher.forceActiveFocus() }
                  onDoubleClicked: { root.selectedIndex = row.index; root.openSelected() }
                }
              }
            }

            Rectangle {
              width: Style.normalBorderWidth
              height: parent.height
              color: root.border
              opacity: 0.3
            }

            Flickable {
              id: previewFlick
              width: parent.width * 0.56 - Style.normalBorderWidth
              height: parent.height
              contentWidth: width
              contentHeight: previewColumn.implicitHeight
              clip: true
              boundsBehavior: Flickable.StopAtBounds

              Column {
                id: previewColumn
                width: previewFlick.width - root.contentMargin
                x: root.contentMargin
                spacing: root.gap

                Text {
                  textFormat: Text.PlainText
                  width: parent.width
                  visible: !!root.selectedItem
                  text: {
                    var it = root.selectedItem
                    if (!it) return ""
                    var tags = Array.isArray(it.tags) ? it.tags.map(function(t) { return "#" + t }).join(" ") : ""
                    return (it.subtype ? it.subtype + "   " : "") + tags
                  }
                  color: root.accent
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.caption
                  font.bold: true
                  elide: Text.ElideRight
                }
                Text {
                  textFormat: Text.PlainText
                  width: parent.width
                  text: root.selectedItem ? String(root.selectedItem.improved || "") : ""
                  color: root.foreground
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.caption
                  wrapMode: Text.Wrap
                }
              }
            }
          }
        }
      }
    }
  }
}
