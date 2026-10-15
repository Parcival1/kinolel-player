//
// Created by Tobias Hieta on 18/03/16.
//

#include <QCoreApplication>
#include <QPushButton>
#include <QDesktopServices>

#include "system/SystemComponent.h"
#include "settings/SettingsComponent.h"
#include "ErrorMessage.h"
#include "shared/Names.h"

/////////////////////////////////////////////////////////////////////////////////////////
ErrorMessage::ErrorMessage(const QString& errorMessage, bool allowResetConfig)
  : QMessageBox(nullptr)
{
  setIcon(Critical);
  // KinoLel: Texte Deutsch, Name aus marke.cmake
  setText(Names::AppName() + QString::fromUtf8(" hat einen schweren Fehler und muss beendet werden."));
  setDetailedText(errorMessage);
  setInformativeText(QString::fromUtf8("„Zurücksetzen“ stellt die Einstellungen des Players zurück und startet neu. "
                                       "„Abbrechen“ beendet das Programm."));
  setWindowTitle(Names::AppName() + " – Fehler");

  auto exitButton = addButton(Abort);
  auto helpButton = addButton(Help);

  QPushButton* resetButton = nullptr;
  if (allowResetConfig)
    resetButton = addButton(Reset);

  connect(this, &QMessageBox::buttonClicked, [=](QAbstractButton* button)
  {
    if (button == exitButton)
    {
      qApp->quit();
    }
    else if (button == resetButton)
    {
      SettingsComponent::resetAndSaveOldConfiguration();
      SystemComponent::restart();
    }
    else if (button == helpButton)
    {
      QDesktopServices::openUrl(QUrl(Names::AppUrl()));
    }
  });
}


