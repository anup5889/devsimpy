# -*- coding: utf-8 -*-

## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ##
# SimulationGUI.py ---
#                     --------------------------------
#                        Copyright (c) 2013
#                       Laurent CAPOCCHI
#                      University of Corsica
#                     --------------------------------
# Version 3.0                                        last modified: 30/11/10
## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ##
#
# GENERAL NOTES AND REMARKS:
#
## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ##

## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ##
#
# GLOBAL VARIABLES AND FUNCTIONS
#
## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ##

import os
import sys
import copy
import threading
import wx
# to send event
if wx.VERSION_STRING < '2.9':
	from wx.lib.pubsub import Publisher
else:
	from wx.lib.pubsub import pub as Publisher

from tempfile import gettempdir
import __builtin__
import traceback

import Core.Utilities.Utilities as Utilities
import Core.Utilities.pluginmanager as pluginmanager
import Core.DEVSKernel.FastSimulator as FastSimulator
import Core.DEVSKernel.DEVS as DEVS
import Core.Components.Decorators as Decorators
from Core.Patterns.Strategy import *

_ = wx.GetTranslation


class FloatSlider(wx.Slider):
	def GetValue(self):
		return (float(wx.Slider.GetValue(self))) / self.GetMax()


class TextObjectValidator(wx.PyValidator):
	""" TextObjectValidator()
	"""

	def __init__(self):
		wx.PyValidator.__init__(self)

	def Clone(self):
		return TextObjectValidator()

	def Validate(self, win):
		textCtrl = self.GetWindow()
		text = textCtrl.GetValue()

		if (len(text) == 0) or (not Utilities.IsAllDigits(text)) or (float(text) <= 0.0):
			wx.MessageBox(_("The field must contain some positive numbers!"), _("Error"))
			textCtrl.SetBackgroundColour("pink")
			textCtrl.SetFocus()
			textCtrl.Refresh()
			return False
		else:
			textCtrl.SetBackgroundColour(wx.SystemSettings_GetColour(wx.SYS_COLOUR_WINDOW))
			textCtrl.Refresh()
			return True

	def TransferToWindow(self):
		return True # Prevent wxDialog from complaining.

	def TransferFromWindow(self):
		return True # Prevent wxDialog from complaining.


class CollapsiblePanel(wx.Panel):
	def __init__(self, parent, simdia):

		wx.Panel.__init__(self, parent, -1)

		self.parent = parent
		### frame or panel !!!
		self.simdia = simdia

		self.org_w, self.org_h = self.simdia.GetSize()

		self.label1 = _("More settings...")
		self.label2 = _("extra options")

		self.cp = cp = wx.CollapsiblePane(self, label=self.label1,
										  style=wx.CP_DEFAULT_STYLE | wx.CP_NO_TLW_RESIZE)
		self.Bind(wx.EVT_COLLAPSIBLEPANE_CHANGED, self.OnPaneChanged, cp)
		self.MakePaneContent(cp.GetPane())

		sizer = wx.BoxSizer(wx.VERTICAL)
		self.SetSizer(sizer)
		sizer.Add(cp, 0, wx.RIGHT | wx.LEFT | wx.EXPAND, 9)

	def OnPaneChanged(self, evt=None):

		# redo the layout
		self.Layout()

		### new height to apply
		new_h = self.cp.GetSize()[-1]

		# and also change the labels
		if self.cp.IsExpanded():
			### change the collapsible lable
			self.cp.SetLabel(self.label2)
			### adapte the window size
			self.simdia.SetSizeWH(-1, self.org_h + new_h)
			### Max limite
			self.simdia.SetMaxSize(wx.Size(self.simdia.GetSize()[0], self.org_h + new_h))
		else:
			### change the collapsible lable
			self.cp.SetLabel(self.label1)
			### adapte the window size
			self.simdia.SetSizeWH(-1, self.org_h)

	def MakePaneContent(self, pane):
		"""Just make a few controls to put on the collapsible pane"""

		text2 = wx.StaticText(pane, wx.ID_ANY, _("Select algorithm:"))
		ch1 = wx.Choice(pane, wx.ID_ANY, choices=self.simdia.simulators_dict.keys())
		text3 = wx.StaticText(pane, wx.ID_ANY, _("Profiling"))
		cb1 = wx.CheckBox(pane, wx.ID_ANY, name='check_prof')
		text4 = wx.StaticText(pane, wx.ID_ANY, _("No time limit"))
		cb2 = wx.CheckBox(pane, wx.ID_ANY, name='check_ntl')

		if not 'hotshot' in sys.modules.keys():
			text3.Enable(False)
			cb1.Enable(False)
			self.parent.prof = False

		cb2.SetValue(__builtin__.__dict__['NTL'])

		### default strategy
		ch1.SetSelection(self.simdia.simulators_dict.values().index(self.simdia.selected_strategy))

		ch1.SetToolTipString(_("Select the simulator strategy."))
		cb1.SetToolTipString(_("For simulation profiling using hotshot"))
		cb2.SetToolTipString(_("No time limit for the simulation. Simulation is over when childs are no active."))

		grid3 = wx.GridSizer(3, 2)
		grid3.Add(text2, 0, wx.ALIGN_LEFT, 19)
		grid3.Add(ch1, 1, wx.ALIGN_RIGHT)
		grid3.Add(text3, 0, wx.ALIGN_LEFT, 19)
		grid3.Add(cb1, 1, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_HORIZONTAL, 19)
		grid3.Add(text4, 0, wx.ALIGN_LEFT, 19)
		grid3.Add(cb2, 1, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_HORIZONTAL, 19)

		pane.SetSizer(grid3)

		self.Bind(wx.EVT_CHOICE, self.OnChoice, ch1)
		self.Bind(wx.EVT_CHECKBOX, self.OnProfiling, cb1)
		self.Bind(wx.EVT_CHECKBOX, self.OnNTL, cb2)

	###
	def OnChoice(self, event):
		""" strategy choice has been invoked
		"""
		selected_string = event.GetString()
		if self.simdia.simulators_dict.has_key(selected_string):
			self.simdia.selected_strategy = self.simdia.simulators_dict[selected_string]
			__builtin__.__dict__['DEFAULT_SIM_STRATEGY'] = self.simdia.selected_strategy

	def OnNTL(self, event):
		cb2 = event.GetEventObject()

		self.simdia.ntl = cb2.GetValue()
		self.simdia._text1.Enable(not self.simdia.ntl)
		self.simdia._value.Enable(not self.simdia.ntl)
		__builtin__.__dict__['NTL'] = self.simdia.ntl

	def OnProfiling(self, event):
		cb1 = event.GetEventObject()

		self.simdia.prof = cb1.GetValue()

#-----------------------------------------------------------------


class SimulationDialog(wx.Frame, wx.Panel):
	""" SimulationDialog(parent, id, title, master)
		
		Frame or Panel with progress bar
	"""

	def __init__(self, parent, id, title, master):
		""" Constructor
		"""

		if isinstance(parent, wx.Panel):
			wx.Panel.__init__(self, parent, id)
			self.SetBackgroundColour(wx.NullColour)
			self.panel = self

			### panel herite of the left spiltter size
			self.panel.SetSize(parent.GetParent().GetSize())

			# status bar de l'application principale
			self.statusbar = parent.GetTopLevelParent().statusbar
		else:
			wx.Frame.__init__(self, parent, id, title, size=(260, 160),
							  style=wx.DEFAULT_FRAME_STYLE
									| wx.FRAME_FLOAT_ON_PARENT        # forces the window to be on top / non-modal
			)

			# empeche d'etirer la frame
			self.SetMinSize(self.GetSize())

			self.panel = wx.Panel(self, -1)
			#self.statusbar = parent.statusbar if parent else wx.StatusBar(None, wx.ID_ANY)

			wx.CallAfter(self.CreateBar)

			self.__set_properties()

		# local copy
		self.parent = parent
		self.master = master
		self.title = title

		### current master for multi-simulation without simulationDialog reloading (show OnOk) 
		self.current_master = None

		# simulator strategy
		self.simulators_dict = {'PyDEVS': 'SimStrategy1', 'Hierarchical': 'SimStrategy2', 'Direct Coupling': 'SimStrategy3'}
		self.selected_strategy = DEFAULT_SIM_STRATEGY

		assert self.selected_strategy in self.simulators_dict.values()

		### profiling simulation with hotshot
		self.prof = False

		### No time limit simulation (defined in the builtin dico from .devsimpy file)
		self.ntl = __builtin__.__dict__['NTL']

		# definition du thread, du timer et du compteur pour les % de simulation
		self.thread = None
		self.timer = wx.Timer(self, wx.NewId())
		self.count = 10.0
		self.stdioWin = None

		self.__widgets()
		self.__do_layout()
		self.__set_events()

		### create a pubsub receiver (simple way to communicate with thread)
		Publisher.subscribe(self.ErrorManager, "error")

	def CreateBar(self):
		self.statusbar = self.CreateStatusBar(2)

	def __set_properties(self):
		icon = wx.EmptyIcon()
		icon.CopyFromBitmap(wx.Bitmap(os.path.join(ICON_PATH_16_16, "simulation.png"), wx.BITMAP_TYPE_ANY))
		self.SetIcon(icon)

		self.Center()

	def __widgets(self):

		self._text1 = wx.StaticText(self.panel, wx.ID_ANY, _('Final time'))
		self._value = wx.TextCtrl(self.panel, wx.ID_ANY, str(float(self.master.FINAL_TIME)), validator=TextObjectValidator())
		self._btn1 = wx.Button(self.panel, wx.NewId(), _('Run'))
		self._btn2 = wx.Button(self.panel, wx.NewId(), _('Stop'))
		self._btn3 = wx.Button(self.panel, wx.NewId(), _('Suspend'))
		self._btn4 = wx.Button(self.panel, wx.NewId(), _('Log'))
		self._gauge = wx.Gauge(self.panel, wx.ID_ANY, 100, size=(-1, 25), style=wx.GA_HORIZONTAL | wx.GA_SMOOTH)
		#self._gauge = FloatSlider(self.panel, wx.ID_ANY, 0.0, 0.0, self.master.FINAL_TIME, wx.DefaultPosition, (-1, 35), wx.SL_AUTOTICKS | wx.SL_HORIZONTAL | wx.SL_LABELS)
		self._cp = CollapsiblePanel(self.panel, self)

		self._text1.Enable(not self.ntl)
		self._value.Enable(not self.ntl)

		self._btn1.SetToolTipString(_("Begin simulation process."))
		self._btn2.SetToolTipString(_("Stop the simulation process."))
		self._btn3.SetToolTipString(_("Suspend the simulation process."))
		self._btn4.SetToolTipString(_("Lauch the log window (often depends on some plugins (verbose, activity, ...))."))

	def __do_layout(self):

		vbox_top = wx.BoxSizer(wx.VERTICAL)
		vbox_body = wx.BoxSizer(wx.VERTICAL)

		#panel 1
		grid1 = wx.GridSizer(1, 2)
		grid1.Add(self._text1, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_CENTER_HORIZONTAL)
		grid1.Add(self._value, 0, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_HORIZONTAL)
		vbox_body.Add(grid1, 0, wx.EXPAND, 9)

		# panel2
		grid2 = wx.GridSizer(3, 2, 2, 2)
		grid2.Add(self._btn1, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_CENTER_HORIZONTAL | wx.EXPAND)
		grid2.Add(self._btn3, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_CENTER_HORIZONTAL | wx.EXPAND)
		grid2.Add(self._btn2, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_CENTER_HORIZONTAL | wx.EXPAND)
		grid2.Add(self._btn4, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_CENTER_HORIZONTAL | wx.EXPAND)
		vbox_body.Add(grid2, 0, wx.EXPAND, 9)

		# panel4
		hbox1 = wx.BoxSizer(wx.HORIZONTAL)
		hbox1.Add(self._gauge, 1, wx.EXPAND, 9)
		vbox_body.Add(hbox1, 0, wx.EXPAND, 9)

		## panel5
		hbox2 = wx.BoxSizer(wx.HORIZONTAL)
		hbox2.Add(self._cp)
		vbox_body.Add(hbox2, 0, wx.EXPAND, 9)

		# fin panel
		vbox_top.Add(vbox_body, 0, wx.EXPAND, 9)
		self.panel.SetSizer(vbox_top)

		self._text1.SetFocus()
		self._btn1.SetDefault()
		self._btn2.Disable()
		self._btn3.Disable()

	def __set_events(self):

		# gestionnaires d'evenements
		self.Bind(wx.EVT_BUTTON, self.OnOk, self._btn1)
		self.Bind(wx.EVT_BUTTON, self.OnStop, self._btn2)
		self.Bind(wx.EVT_BUTTON, self.OnSuspend, self._btn3)
		self.Bind(wx.EVT_BUTTON, self.OnViewLog, self._btn4)
		self.Bind(wx.EVT_TIMER, self.OnTimer, self.timer)
		self.Bind(wx.EVT_TEXT, self.OnText, self._value)
		self.Bind(wx.EVT_CLOSE, self.OnQuit)

	###
	def OnText(self, event):
		self._gauge.SetValue(0)

	###
	@Decorators.BuzyCursorNotification
	def OnViewLog(self, event):
		"""	When View button is clicked
		"""
		# The simulation verbose event occurs
		pluginmanager.trigger_event("START_SIM_VERBOSE", parent=self)
		# The simulation verbose event occurs
		pluginmanager.trigger_event("VIEW_ACTIVITY_REPORT", parent=self, master=self.current_master)

	###
	def OnOk(self, event):
		""" When Run button is clicked
		"""

		assert (self.master is not None)
		from Core.Components.Container import Diagram

		if self._value.GetValidator().Validate(self._value) or self.ntl:

			### pour prendre en compte les simulations multiples sans relancer un SimulationDialog
			### si le thread n'est pas lance (pas pendant un suspend)
			if self.thread is not None and not self.thread.thread_suspend:
				diagram = self.master.getBlockModel()
				diagram.Clean()
				self.current_master = Diagram.makeDEVSInstance(diagram)
			else:
				self.current_master = self.master

			if isinstance(self.parent, wx.Panel):
				# redirection du stdout ici dans le cas du Panel (sinon dans OnSimulation)
				mainW = self.parent.GetTopLevelParent()
				sys.stdout = mainW.stdioWin

			### test si le modele et bien charge
			if (self.current_master is None) or (self.current_master.componentSet == []):
				return self.MsgBoxEmptyModel()

			### dont erase the gauge if ntl
			if not self.ntl:
			# stockage du temps de simulation dans le master
				self.current_master.FINAL_TIME = float(self._value.GetValue())
				self._gauge.SetValue(0)
				### if _gauge is wx.Slider
				#self._gauge.SetMax(self.current_master.FINAL_TIME)
			
			self.statusbar.SetBackgroundColour('')
			self.statusbar.SetStatusText("", 1)
			if self.statusbar.GetFieldsCount() > 2:
				self.statusbar.SetStatusText("", 2)

			if (self.thread is None) or (not self.timer.IsRunning()):

				pluginmanager.trigger_event("START_BLINK", parent=self, master=self.current_master)
				pluginmanager.trigger_event("START_TEST", parent=self, master=self.current_master)

				### The START_ACTIVITY_TRACKING event occurs
				pluginmanager.trigger_event("START_ACTIVITY_TRACKING", parent=self, master=self.current_master)

				### The START_CONCURRENT_SIMULATION event occurs
				pluginmanager.trigger_event("START_CONCURRENT_SIMULATION", parent=self, master=self.current_master)

				### clear all log file
				for fn in filter(lambda f: f.endswith('.devsimpy.log'), os.listdir(gettempdir())):
					os.remove(os.path.join(gettempdir(), fn))

				self.thread = SimulationThread(self.current_master, self.selected_strategy, self.prof, self.ntl)
				self.thread.setName(self.title)

				### si le modele n'a pas de couplage, ou si pas de generateur: alors pas besoin de simuler
				if self.thread.end_flag:
					self.OnTimer(event)
				else:
					self.timer.Start(100)
			else:
				#print self.thread.getAlgorithm().trace
				### for back simulation 
				#self.thread.s = shelve.open(self.thread.f.name+'.db',flag = 'r')
				#self.thread.model = self.thread.s['s'][str(float(self._gauge.GetValue()))]

				### restart the hiding gauge
				if self.ntl:
					self._gauge.Show()

				### restart thread
				self.thread.resume_thread()

			self.Interact(False)

			if self.count >= 100:
				return

			# aucune possibilite d'interagir avec le modele
			#self.parent.Enable(False)

	def Interact(self, access=True):
		""" Enabling and disabling options (buttons, checkbox, ...)
		"""

		self._btn1.Enable(access)
		self._btn2.Enable(not access)
		self._btn3.Enable(not access)
		self._value.Enable(not self.ntl)
		self._cp.Enable(access)

	###
	def OnStop(self, event):
		""" When Stop button is cliked
		"""

		self.Interact()
		self.thread.terminate()
		self.timer.Stop()
		wx.Bell()

		self._gauge.SetValue(0)
		self.statusbar.SetBackgroundColour('')
		self.statusbar.SetStatusText(_('Interrupted'), 0)
		self.statusbar.SetStatusText("", 1)
		if self.statusbar.GetFieldsCount() > 2:
			self.statusbar.SetStatusText("", 2)

	###
	def OnSuspend(self, event):
		""" When Stop button is cliked
		"""

		self.Interact()
		self.thread.suspend()

		if self.ntl:
			self._gauge.Hide()

		if self.count == 0 or self.count >= 100 or not self.timer.IsRunning():
			return

		self.statusbar.SetStatusText(_('Suspended'), 0)

		# possibilite d'interagir avec le modele
		#self.parent.Enable(True)
		wx.Bell()

	###
	def OnTimer(self, event):
		""" Give the pourcentage of simulation progress
		"""

		### si no time limite pour la simulation, on pulse sinon on avance vers le temps final
		if self.ntl:
			self._gauge.Pulse()
		else:
			self.count = (self.thread.model.timeLast / self.thread.model.FINAL_TIME) * 100
			self._gauge.SetValue(self.count)

		### si pas de no time limit pour la simulation et que la gauge est pleine
		if self.thread.end_flag:
			self.timer.Stop()

			self._btn1.Enable(True)
			self._btn2.Disable()
			self._btn3.Disable()
			self._value.Enable(not self.ntl)
			self._cp.Enable()

			self.statusbar.SetBackgroundColour('')
			self.statusbar.SetStatusText(_("Completed!"), 0)
			self.statusbar.SetStatusText("%0.4f s" % self.thread.cpu_time, 1)

			if not self.ntl:
				if self.statusbar.GetFieldsCount() > 2:
					self.statusbar.SetStatusText(str(100) + "%", 2)

		elif not self.thread.thread_suspend:
			self.statusbar.SetBackgroundColour('grey')
			self.statusbar.SetStatusText(_("Processing..."), 0)
			self.statusbar.SetStatusText("%0.4f s" % self.thread.cpu_time, 1)
			if not self.ntl:
				if self.statusbar.GetFieldsCount() > 2:
					self.statusbar.SetStatusText(str(self.count)[:4] + "%", 2)

			wx.Yield()

	###
	def MsgBoxEmptyModel(self):
		""" Pop-up alert for empty model
		"""
		dial = wx.MessageDialog(self, _('You want to simulate an empty master model!'), _('Info'), wx.OK)
		if (dial.ShowModal() == wx.ID_OK) and (isinstance(self.parent, wx.Frame)):
			self.DestroyWin()
		else:
			return

	def DestroyWin(self):
		""" To destroy the simulation frame
		"""

		self.statusbar.SetBackgroundColour('')
		self.statusbar.SetFields([""] * self.statusbar.GetFieldsCount())
		try:
			self.parent.stdioWin.frame.Show(False)
		except:
			pass

		try:
		## panel gauche inaccessible
			self.parent.nb1.Enable()

			## menu inaccessible			
			self.parent.tb.Enable()
			for i in xrange(self.parent.menuBar.GetMenuCount()):
				self.parent.menuBar.EnableTop(i, True)

			## autre tab inaccessible
			for p in xrange(self.parent.nb2.GetPageCount()):
				## pour tout les tab non selectionner
				if p != self.parent.nb2.GetSelection():
					self.parent.nb2.GetPage(p).Enable()
		except Exception:
			#sys.stdout.write(_("Empty mode over\n"))
			pass

		self.Destroy()

	def OnQuit(self, event):
		""" When the simulation are stopping
		"""

		# if the simulation is running
		if self.timer.IsRunning():
			dial = wx.MessageDialog(self, _('Are you sure to stop simulation ?'), _('Question'), wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION)
			self.thread.suspend()

			### if ok
			if dial.ShowModal() == wx.ID_YES:
				self.DestroyWin()
				self.thread.terminate()
			else:
				self.thread.resume_thread()
		else:
			self.DestroyWin()

	def ErrorManager(self, msg):
		""" An error is occured. 
		"""
		### simulate event button for the code editor
		from Core.Components.Components import MsgBoxError

		event = wx.PyCommandEvent(wx.EVT_BUTTON.typeId, self._btn1.GetId())

		### try to find the file which have the error from traceback
		try:
			typ, val, tb = msg.data
			trace = traceback.format_exception(typ, val, tb)[-2].split(',')
			path = trace[0]
		except Exception, info:
			path = ""

		devs_error = (os.path.basename(DOMAIN_PATH) in path)

		### if error come from devs python file
		#if devs_error:
		### Error dialog
		if not MsgBoxError(event, self.parent, msg.data):
			### if user dont want correct the error, we destroy the simulation windows
			self.DestroyWin()
		else:
			### is user want to correct error through an editor, we stop simulation process for trying again after the error is corrected.
			self.OnStop(event)
		#else:
			#raise msg

#class BackSimulationDialog(SimulationDialog):
	#""" BackSimulationDialog(parent, id, title, master)
	#An another panel allowing back simulation button
	#"""
	#def __init__(self, *args, **kwargs):
		#SimulationDialog.__init__(self, *args, **kwargs)

	#def __widgets(self):

		#pnl1 = wx.Panel(self.panel, -1)
		#pnl1.SetBackgroundColour(wx.BLACK)
		#pnl2 = wx.Panel(self.panel, -1 )

		#slider1 = wx.Slider(pnl2, -1, 0, 0, 1000)
		#pause = wx.BitmapButton(pnl2, -1, wx.Bitmap('Assets/icons/stock_media-pause.png'))
		#play  = wx.BitmapButton(pnl2, -1, wx.Bitmap('Assets/icons/stock_media-play.png'))
		#next  = wx.BitmapButton(pnl2, -1, wx.Bitmap('Assets/icons/stock_media-next.png'))
		#prev  = wx.BitmapButton(pnl2, -1, wx.Bitmap('Assets/icons/stock_media-prev.png'))

		#vbox = wx.BoxSizer(wx.VERTICAL)
		#hbox1 = wx.BoxSizer(wx.HORIZONTAL)
		#hbox2 = wx.BoxSizer(wx.HORIZONTAL)

		#hbox1.Add(slider1, 1)
		#hbox2.Add(pause)
		#hbox2.Add(play, flag = wx.RIGHT, border = 5)
		#hbox2.Add(next, flag = wx.LEFT, border = 5)
		#hbox2.Add(prev)

		#vbox.Add(hbox1, 1, wx.EXPAND | wx.BOTTOM, 10)
		#vbox.Add(hbox2, 1, wx.EXPAND)
		#pnl2.SetSizer(vbox)

		#sizer = wx.BoxSizer(wx.VERTICAL)
		#sizer.Add(pnl1, 1, flag = wx.EXPAND)
		#sizer.Add(pnl2, flag = wx.EXPAND | wx.BOTTOM | wx.TOP, border = 10)

#--------------------------------------------------------------


class SimulationThread(threading.Thread, FastSimulator.Simulator):
	""" SimulationThread(model)
		
		Thread for DEVS simulation task
	"""

	def __init__(self, model=None, strategy='', prof=False, ntl=False):
		""" Constructor
		"""
		threading.Thread.__init__(self)
		FastSimulator.Simulator.__init__(self, model)

		### local copy
		self.strategy = strategy
		self.prof = prof
		self.ntl = ntl

		self.end_flag = False
		self.thread_suspend = False
		self.sleep_time = 0.0
		self.thread_sleep = False
		self.cpu_time = -1

		self.start()

	@Decorators.hotshotit
	def run(self):
		""" Run thread
		"""

		### define the simulation strategy
		args = {'simulator': self}
		cls_str = eval(eval('self.strategy'))
		self.setAlgorithm(apply(cls_str, (), args))

		while not self.end_flag:
			### traceback exception engine for .py file
			try:
				self.simulate(self.model.FINAL_TIME)
			except Exception, info:
				self.terminate(error=True, msg=sys.exc_info())

	def terminate(self, error=False, msg=None):
		""" Thread termination routine
			param error: False if thread is terminate without error
			param msg: message to submit
		"""

		if not self.end_flag:
			if error:

				###for traceback
				etype = msg[0]
				evalue = msg[1]
				etb = traceback.extract_tb(msg[2])
				sys.stderr.write('Error in routine: your routine here\n')
				sys.stderr.write('Error Type: ' + str(etype) + '\n')
				sys.stderr.write('Error Value: ' + str(evalue) + '\n')
				sys.stderr.write('Traceback: ' + str(etb) + '\n')

				wx.CallAfter(Publisher.sendMessage, "error", msg)

				### error sound
				if __builtin__.__dict__['GUI_FLAG'] is True:
					wx.CallAfter(Utilities.playSound, SIMULATION_ERROR_WAV_PATH)
			else:
				for m in filter(lambda a: isinstance(a, DEVS.AtomicDEVS), self.model.componentSet):
					### call finished method
					Publisher.sendMessage('%d.finished' % (id(m)))
				if __builtin__.__dict__['GUI_FLAG'] is True:
					wx.CallAfter(Utilities.playSound, SIMULATION_SUCCESS_WAV_PATH)

		self.end_flag = True

	def set_sleep(self, sleeptime):
		self.thread_sleep = True
		self._sleeptime = sleeptime

	def suspend(self):
		self.thread_suspend = True

	def resume_thread(self):
		self.thread_suspend = False

### ------------------------------------------------------------


class TestApp(wx.App):
	""" Testing application
	"""

	def OnInit(self):
		import gettext
		import DomainInterface.MasterModel

		__builtin__.__dict__['ICON_PATH_16_16'] = os.path.join('Assets','icons', '16x16')
		__builtin__.__dict__['DEFAULT_SIM_STRATEGY'] = 'SimStrategy2'
		__builtin__.__dict__['NTL'] = False
		__builtin__.__dict__['_'] = gettext.gettext

		self.frame = SimulationDialog(None, wx.ID_ANY, 'Simulator', Core.DomainInterface.MasterModel.Master())
		self.frame.Show()
		return True

	def OnQuit(self, event):
		self.Close()


if __name__ == '__main__':
	app = TestApp(0)
	app.MainLoop()