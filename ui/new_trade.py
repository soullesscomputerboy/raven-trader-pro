from jsonrpcclient.requests import Request
from requests import post, get
from decimal import *

from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5 import uic

import sys, getopt, argparse, json, time, getpass, os.path
from util import *
from rvn_rpc import *

from swap_transaction import SwapTransaction
from swap_trade import SwapTrade

class NewTradeDialog(QDialog):
  def __init__(self, swap_storage, prefill=None, parent=None, **kwargs):
    super().__init__(parent, **kwargs)
    uic.loadUi("ui/qt/new_trade.ui", self)
    self.swap_storage = swap_storage
    
    self.swap_storage.update_wallet()
    self.waiting_txid = None
    self.asset_exists = True
    self.all_utxo = False #allow perfectly rounded UTXO's only when waiting from the start

    self.setWindowTitle("New Trade Order")
    self.cmbOwnAsset.setEditable(False)
    self.cmbOwnAsset.addItems(["{} [{}]".format(v, self.swap_storage.assets[v]["balance"]) for v in self.swap_storage.my_asset_names])
    self.cmbWantAsset.addItems(self.swap_storage.my_asset_names)
    self.cmbWantAsset.setCurrentText("")

    if prefill:
      self.cmbOwnAsset.setCurrentText(prefill["asset"])
      self.spinOwnQuantity.setValue(prefill["quantity"])
      self.asset_exists = True

    self.cmbOwnAsset.currentIndexChanged.connect(self.update)
    self.cmbWantAsset.currentIndexChanged.connect(self.update)
    self.cmbWantAsset.currentTextChanged.connect(self.asset_changed)
    self.spinOwnQuantity.valueChanged.connect(self.update)
    self.spinWantQuantity.valueChanged.connect(self.update)
    self.spinOrderCount.valueChanged.connect(self.update)

    self.btnCheckAvailable.clicked.connect(self.check_available)
    self.update()


  def check_available(self):
    #TODO: Save this asset data for later
    asset_name = self.cmbWantAsset.currentText().replace("!", "")
    want_admin = False
    if(asset_name[-1:] == "!"):
      want_admin = True
      asset_name = asset_name[:-1]#Take all except !
    details = do_rpc("getassetdata", asset_name=asset_name)
    self.asset_exists = True if details else False
    self.btnCheckAvailable.setEnabled(False)
    if self.asset_exists:
      self.spinWantQuantity.setEnabled(True)
      self.btnCheckAvailable.setText("Yes! - {} total".format(details["amount"]))
      self.spinWantQuantity.setMaximum(float(details["amount"]))
    else:
      self.spinWantQuantity.setEnabled(False)
      self.btnCheckAvailable.setText("No!")
    self.update()

  def asset_changed(self):
    self.asset_exists = False
    self.btnCheckAvailable.setText("Check Available")
    self.btnCheckAvailable.setEnabled(True)
    self.update()
      
  def update(self):
    #Read GUI
    self.own_quantity = self.spinOwnQuantity.value()
    self.want_quantity = self.spinWantQuantity.value()
    self.destination = self.txtDestination.text()
    self.order_count = self.spinOrderCount.value()
    self.valid_order = True

    self.own_asset_name = self.swap_storage.my_asset_names[self.cmbOwnAsset.currentIndex()]
    self.want_asset_name = self.cmbWantAsset.currentText()
    self.lblSummary.setText("Give: {:.8g}x [{}], Get: {:.8g}x [{}]".format(self.own_quantity, self.own_asset_name, self.want_quantity, self.want_asset_name))
    self.lblFinal.setText("Give: {:.8g}x [{}], Get: {:.8g}x [{}]".format(self.own_quantity * self.order_count, self.own_asset_name, self.want_quantity * self.order_count, self.want_asset_name))
    #Don't own the asset or enough of it
    if self.own_asset_name not in self.swap_storage.my_asset_names or self.own_quantity > self.swap_storage.assets[self.own_asset_name]["balance"]:
      self.valid_order = False

    #Not valid while waiting on a tx to confirm or if asset hasn't been confirmed yet
    if self.waiting_txid or not self.asset_exists:
      self.valid_order = False

    #Update GUI
    #Hide the button if we don't have a valid order
    if self.valid_order:
      self.btnDialogButtons.setStandardButtons(QDialogButtonBox.Cancel | QDialogButtonBox.Ok)
    else:
      self.btnDialogButtons.setStandardButtons(QDialogButtonBox.Cancel)

  def build_trade(self):
    return SwapTrade.create_trade("trade", self.own_asset_name, self.own_quantity, self.want_asset_name, self.want_quantity, self.order_count, self.destination)