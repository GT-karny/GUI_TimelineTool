from PyQt5 import QtWidgets, QtCore
import pyqtgraph as pg
import numpy as np
from ..core.timeline import Timeline, Keyframe, InterpMode
from ..core.interpolation import evaluate
from ..io.csv_exporter import export_csv

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Timeline Editor (P0)")
        self.resize(1100, 700)
        self.timeline = Timeline()
        self.sample_rate = 90.0

        self.plot = pg.PlotWidget(background="w")
        self.plot.showGrid(x=True, y=True, alpha=0.3)
        self.plot.setLabel("bottom", "Time (s)"); self.plot.setLabel("left", "Value")
        self.curve = self.plot.plot([], [], pen=pg.mkPen(width=2))
        self.points = pg.ScatterPlotItem(size=10, brush=pg.mkBrush(40,120,255,180), pen=pg.mkPen(0,60,160,200))
        self.plot.addItem(self.points)
        self.playhead = pg.InfiniteLine(pos=0.0, angle=90, movable=False, pen=pg.mkPen(200,0,0,200))
        self.plot.addItem(self.playhead)

        tb = QtWidgets.QToolBar(); self.addToolBar(tb)
        self.mode = QtWidgets.QComboBox(); self.mode.addItems(["cubic","linear","step"])
        tb.addWidget(QtWidgets.QLabel("Interpolation: ")); tb.addWidget(self.mode)
        self.dur = QtWidgets.QDoubleSpinBox(); self.dur.setRange(0.1,10000); self.dur.setValue(self.timeline.duration_s); self.dur.setSuffix(" s")
        tb.addWidget(QtWidgets.QLabel("Duration: ")); tb.addWidget(self.dur)
        self.rate = QtWidgets.QDoubleSpinBox(); self.rate.setRange(1.0,1000.0); self.rate.setDecimals(1); self.rate.setValue(self.sample_rate); self.rate.setSuffix(" Hz")
        tb.addWidget(QtWidgets.QLabel("Sample: ")); tb.addWidget(self.rate)
        self.btn_add = QtWidgets.QPushButton("Add Key"); self.btn_del = QtWidgets.QPushButton("Delete Key"); self.btn_reset = QtWidgets.QPushButton("Reset")
        tb.addWidget(self.btn_add); tb.addWidget(self.btn_del); tb.addWidget(self.btn_reset)
        self.btn_export = QtWidgets.QPushButton("Export CSV"); tb.addWidget(self.btn_export)
        self.btn_play = QtWidgets.QPushButton("▶"); self.btn_stop = QtWidgets.QPushButton("■")
        tb.addWidget(self.btn_play); tb.addWidget(self.btn_stop)

        central = QtWidgets.QWidget(); lay = QtWidgets.QVBoxLayout(central); lay.addWidget(self.plot); self.setCentralWidget(central)
        self.status = QtWidgets.QStatusBar(); self.setStatusBar(self.status)

        self.dragging = False; self.drag_index = None
        self.timer = QtWidgets.QTimer(); self.timer.timeout.connect(self.on_tick); self.t0 = None

        self.mode.currentIndexChanged.connect(self.on_mode)
        self.dur.valueChanged.connect(self.on_duration)
        self.rate.valueChanged.connect(self.on_rate)
        self.btn_add.clicked.connect(self.add_key_at_playhead)
        self.btn_del.clicked.connect(self.delete_nearest_key)
        self.btn_reset.clicked.connect(self.reset_keys)
        self.btn_export.clicked.connect(self.do_export)
        self.btn_play.clicked.connect(self.play); self.btn_stop.clicked.connect(self.stop)

        self.points.sigClicked.connect(self.on_point_clicked)
        self.plot.scene().sigMouseMoved.connect(self.on_mouse_move)
        self.plot.scene().sigMouseClicked.connect(self.on_mouse_click)

        self.update_plot()

    def on_mode(self, idx):
        m = self.mode.currentText()
        self.timeline.track.interp = {"cubic":InterpMode.CUBIC, "linear":InterpMode.LINEAR, "step":InterpMode.STEP}[m]
        self.update_plot()

    def on_duration(self, val): self.timeline.set_duration(float(val)); self.update_plot()
    def on_rate(self, val): self.sample_rate = float(val)

    def reset_keys(self):
        self.timeline.track.keys = [Keyframe(0.0,0.0), Keyframe(max(5.0,self.timeline.duration_s),0.0)]
        self.update_plot()

    def add_key_at_playhead(self):
        t = float(self.playhead.value())
        v = float(evaluate(self.timeline.track, np.array([t]))[0])
        self.timeline.track.keys.append(Keyframe(t,v)); self.timeline.track.clamp_times(); self.update_plot()

    def delete_nearest_key(self):
        ks = self.timeline.track.sorted()
        if len(ks) <= 2: return
        import numpy as np
        t = float(self.playhead.value())
        idx = int(np.argmin(np.abs(np.array([k.t for k in ks]) - t)))
        self.timeline.track.keys.remove(ks[idx]); self.update_plot()

    def on_point_clicked(self, plt, pts):
        if not pts: return
        p = pts[0]; self.dragging = True; self.drag_index = p.data()
        self.plot.scene().sigMouseMoved.connect(self.on_drag_move)
        self.plot.scene().sigMouseClicked.connect(self.on_drag_release)

    def on_drag_move(self, pos):
        if not self.dragging: return
        mp = self.plot.plotItem.vb.mapSceneToView(pos)
        ks_sorted = self.timeline.track.sorted()
        idx = self.drag_index
        if idx is None or idx<0 or idx>=len(ks_sorted): return
        actual = self.timeline.track.keys.index(ks_sorted[idx])
        self.timeline.track.keys[actual].t = float(max(0.0, mp.x()))
        self.timeline.track.keys[actual].v = float(mp.y())
        self.timeline.track.clamp_times(); self.update_plot()

    def on_drag_release(self, evt):
        if self.dragging:
            self.dragging = False; self.drag_index = None
            try:
                self.plot.scene().sigMouseMoved.disconnect(self.on_drag_move)
                self.plot.scene().sigMouseClicked.disconnect(self.on_drag_release)
            except Exception: pass

    def on_mouse_move(self, pos):
        mp = self.plot.plotItem.vb.mapSceneToView(pos)
        self.status.showMessage(f"t={mp.x():.3f}s, v={mp.y():.3f}")

    def on_mouse_click(self, evt):
        if evt.button() == QtCore.Qt.MouseButton.RightButton:
            mp = self.plot.plotItem.vb.mapSceneToView(evt.scenePos())
            self.playhead.setValue(max(0.0, float(mp.x())))

    def play(self):
        self.t0 = QtCore.QTime.currentTime(); self.timer.start(int(1000/60))

    def stop(self): self.timer.stop()

    def on_tick(self):
        if self.t0 is None: return
        elapsed = self.t0.msecsTo(QtCore.QTime.currentTime())/1000.0
        t = elapsed % max(1e-6, self.timeline.duration_s)
        self.playhead.setValue(t)

    def do_export(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Export CSV", "timeline.csv", "CSV Files (*.csv)")
        if not path: return
        export_csv(path, self.timeline, self.sample_rate)
        QtWidgets.QMessageBox.information(self, "Export", f"Exported to:\n{path}")

    def update_plot(self):
        import numpy as np
        tmax = max(self.timeline.duration_s, max((k.t for k in self.timeline.track.keys), default=0.0))
        self.plot.setXRange(0, max(1.0, tmax), padding=0.02)
        dense_t = np.linspace(0.0, max(1e-3, tmax), 1000)
        dense_v = evaluate(self.timeline.track, dense_t)
        self.curve.setData(dense_t, dense_v)
        ks = self.timeline.track.sorted()
        self.points.setData([{'pos': (ks[i].t, ks[i].v), 'data': i} for i in range(len(ks))])
