from PySide6.QtCore import QThread, Signal
from PySide6.QtTest import QTest

import gui.sprite.ml_install_dialog as mid
from gui.sprite.ml_install_dialog import SpriteMLInstallDialog

SPECS = ["mediapipe>=0.10", "rembg[cpu]>=2.0"]


def test_packages_exclude_rembg_when_python_is_gated(qapp, monkeypatch):
    monkeypatch.setattr(mid, "sprite_ml_packages", lambda: (list(SPECS), ""))
    monkeypatch.setattr(mid, "python_supports_rembg", lambda: False)
    dialog = SpriteMLInstallDialog()
    assert dialog.packages() == ["mediapipe>=0.10"]
    assert dialog.rembg_gated()
    assert not dialog.gate_label.isHidden()
    dialog.done(0)


def test_packages_include_rembg_when_supported(qapp, monkeypatch):
    monkeypatch.setattr(mid, "sprite_ml_packages", lambda: (list(SPECS), ""))
    monkeypatch.setattr(mid, "python_supports_rembg", lambda: True)
    dialog = SpriteMLInstallDialog()
    assert dialog.packages() == SPECS
    assert not dialog.rembg_gated()
    assert dialog.gate_label.isHidden()
    dialog.done(0)


class _FakeInstaller(QThread):
    progress = Signal(str)
    finished = Signal(bool, str)
    percentage = Signal(int)

    def __init__(self, packages, update_requirements=True, index_url=None):
        super().__init__()
        self.packages = list(packages)
        self.update_requirements = update_requirements
        self.index_url = index_url

    def run(self):
        self.progress.emit("fake install line")
        self.percentage.emit(100)
        self.finished.emit(True, "fake ok")


def test_start_install_runs_installer_and_emits(qapp, monkeypatch):
    monkeypatch.setattr(mid, "sprite_ml_packages", lambda: (list(SPECS), ""))
    monkeypatch.setattr(mid, "python_supports_rembg", lambda: True)
    monkeypatch.setattr(mid, "PackageInstaller", _FakeInstaller)
    dialog = SpriteMLInstallDialog()
    got = []
    dialog.installFinished.connect(got.append)
    dialog.start_install()
    assert dialog.is_running() or got == [True]
    for _ in range(200):
        if got:
            break
        QTest.qWait(20)
    assert got == [True]
    assert "fake install line" in dialog.console.console.toPlainText()
    assert dialog._installer.update_requirements is False
    assert dialog._installer.index_url is None  # "" from sprite_ml_packages → PyPI default
    assert dialog.close_btn.isEnabled()
    dialog.done(0)


def test_reject_is_blocked_while_running(qapp, monkeypatch):
    monkeypatch.setattr(mid, "sprite_ml_packages", lambda: (list(SPECS), ""))
    monkeypatch.setattr(mid, "python_supports_rembg", lambda: True)

    class _Slow(_FakeInstaller):
        def run(self):
            QThread.msleep(150)
            self.finished.emit(True, "slow ok")

    monkeypatch.setattr(mid, "PackageInstaller", _Slow)
    shown = []
    monkeypatch.setattr(mid.QMessageBox, "warning", staticmethod(lambda *a, **k: shown.append(a)))
    dialog = SpriteMLInstallDialog()
    dialog.show()
    dialog.start_install()
    dialog.reject()
    assert shown and dialog.isVisible()
    assert dialog._installer.wait(5000), "fake installer did not finish"
    QTest.qWait(20)
    dialog.reject()
    assert not dialog.isVisible()
