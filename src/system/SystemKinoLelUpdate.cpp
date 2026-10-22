// KinoLel: Auto-Update (Lel 16.10.: „Wir können nicht einbauen, dass die App sich automatisch updatet?“)
//
// Beim Start (und alle 12 Stunden, höchstens alle 6 Stunden) fragt die App die GitHub-Releases von APP_UPDATE_REPO ab.
// Gibt es eine neuere Version, zeigt die Weboberfläche einen Hinweis (native/updatePlugin.js). Mit einem Klick lädt die
// App den Installer, startet ihn still (/SILENT) und beendet sich; der Installer startet KinoLel danach neu.
// Portabel: nur Hinweis mit Link zur Release-Seite. MSIX (Microsoft Store): keine Prüfung, der Store aktualisiert.
#include <algorithm>
#include <QCoreApplication>
#include <QDateTime>
#include <QDir>
#include <QFile>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QNetworkReply>
#include <QNetworkRequest>
#include <QPointer>
#include <QProcess>
#include <QRegularExpression>
#include <QSettings>
#include <QStandardPaths>
#include <QTimer>
#include <QVersionNumber>

#include "SystemComponent.h"
#include "Names.h"
#include "Paths.h"
#include "Version.h"

#ifdef Q_OS_WIN
#include <windows.h>
#include <appmodel.h>
#endif

namespace
{
  bool istMsixPaket()
  {
#ifdef Q_OS_WIN
    UINT32 laenge = 0;
    return GetCurrentPackageFullName(&laenge, nullptr) != APPMODEL_ERROR_NO_PACKAGE;
#else
    return false;
#endif
  }

  QVersionNumber versionAus(const QString& text)
  {
    QString v = text.trimmed();
    if (v.startsWith('v') || v.startsWith('V'))
      v.remove(0, 1);
    return QVersionNumber::fromString(v);
  }
}

///////////////////////////////////////////////////////////////////////////////////////////////////
void SystemComponent::kinolelUpdatePruefen(bool sofort)
{
#ifndef Q_OS_WIN
  return;  // Auto-Update nur für den Windows-Installer
#endif
  if (istMsixPaket())
    return;

  // Lel 22.10.2026: bei jedem Start der App prüfen (früher höchstens alle 6 Stunden) – nur gegen schnelles Neuladen
  // der Seite höchstens einmal pro Minute. Gefragt wird zuerst die Versionsliste auf kinolel.de (kein Abfragelimit),
  // GitHub nur, wenn sie nicht erreichbar ist (dort ohne Anmeldung 60 Abfragen/Stunde je Internetanschluss).
  QSettings einstellungen;
  const qint64 jetzt = QDateTime::currentSecsSinceEpoch();
  const qint64 zuletzt = einstellungen.value("kinolel/updateZuletzt", 0).toLongLong();
  // KINOLEL_TEST_VERSION: nur für den automatischen Test im Build (gibt eine ältere eigene Version vor)
  if (qEnvironmentVariableIsSet("KINOLEL_TEST_VERSION"))
    sofort = true;
  if (!sofort && jetzt - zuletzt < 60)
    return;
  einstellungen.setValue("kinolel/updateZuletzt", jetzt);

  const QVersionNumber aktuell = versionAus(qEnvironmentVariable("KINOLEL_TEST_VERSION", Version::GetVersionString()));
  auto melden = [this, aktuell](const QVersionNumber& beste, const QString& url, const QString& seite) {
    if (url.isEmpty() || beste.isNull() || QVersionNumber::compare(beste, aktuell) <= 0)
    {
      qInfo() << "KinoLel-Update: aktuell (" << aktuell.toString() << ")";
      return;
    }
    const bool einKlick = !Paths::isPortableMode();
    qInfo() << "KinoLel-Update: neue Version" << beste.toString() << "verfügbar, ein Klick:" << einKlick;
    emit kinolelUpdateVerfuegbar(beste.toString(), url, seite, einKlick);
  };

  auto ausGithub = [this, aktuell, melden]() {
    QNetworkRequest anfrage(QUrl(QString("https://api.github.com/repos/%1/releases?per_page=10").arg(Names::UpdateRepo())));
    anfrage.setHeader(QNetworkRequest::UserAgentHeader, getUserAgent());
    anfrage.setRawHeader("Accept", "application/vnd.github+json");
    anfrage.setAttribute(QNetworkRequest::RedirectPolicyAttribute, QNetworkRequest::NoLessSafeRedirectPolicy);
    QNetworkReply* antwort = m_networkManager->get(anfrage);
    setReplyTimeout(antwort, 20000);
    connect(antwort, &QNetworkReply::finished, this, [antwort, aktuell, melden]() {
      antwort->deleteLater();
      if (antwort->error() != QNetworkReply::NoError)
      {
        qWarning() << "KinoLel-Update: Abfrage fehlgeschlagen:" << antwort->errorString();
        return;
      }
      QVersionNumber beste = aktuell;
      QString url, seite;
      for (const QJsonValue& wert : QJsonDocument::fromJson(antwort->readAll()).array())
      {
        const QJsonObject release = wert.toObject();
        if (release.value("draft").toBool())
          continue;
        const QVersionNumber v = versionAus(release.value("tag_name").toString());
        if (v.isNull() || QVersionNumber::compare(v, beste) <= 0)
          continue;
        for (const QJsonValue& anhang : release.value("assets").toArray())
        {
          const QString name = anhang.toObject().value("name").toString();
          if (name.contains("-Setup-") && name.endsWith(".exe", Qt::CaseInsensitive))
          {
            beste = v;
            url = anhang.toObject().value("browser_download_url").toString();
            seite = release.value("html_url").toString();
          }
        }
      }
      melden(beste, url, seite);
    });
  };

  // Versionsliste aller KinoLel-Apps (stündlich aus den GitHub-Releases, CT 103 /dokumentation/werkzeuge/apps_links.py)
  QNetworkRequest liste(QUrl(Names::ServerUrl() + "/web/kinolel/apps.json"));
  liste.setHeader(QNetworkRequest::UserAgentHeader, getUserAgent());
  liste.setAttribute(QNetworkRequest::CacheLoadControlAttribute, QNetworkRequest::AlwaysNetwork);
  liste.setAttribute(QNetworkRequest::RedirectPolicyAttribute, QNetworkRequest::NoLessSafeRedirectPolicy);
  QNetworkReply* antwort = m_networkManager->get(liste);
  setReplyTimeout(antwort, 15000);
  connect(antwort, &QNetworkReply::finished, this, [antwort, melden, ausGithub]() {
    antwort->deleteLater();
    QJsonObject eintrag;
    if (antwort->error() == QNetworkReply::NoError)
      eintrag = QJsonDocument::fromJson(antwort->readAll()).object().value("windows").toObject();
    const QString url = eintrag.value("url").toString();
    if (url.isEmpty())
    {
      qWarning() << "KinoLel-Update: Versionsliste nicht lesbar (" << antwort->errorString() << "), frage GitHub";
      ausGithub();
      return;
    }
    melden(versionAus(eintrag.value("version").toString()), url, eintrag.value("seite").toString());
  });
}

///////////////////////////////////////////////////////////////////////////////////////////////////
void SystemComponent::kinolelUpdateInstallieren(const QString& url, const QString& version)
{
  const QUrl quelle(url);
  // Nur Installer aus dem eigenen GitHub-Repo laden
  if (quelle.scheme() != "https" || quelle.host() != "github.com" ||
      !quelle.path().startsWith("/" + Names::UpdateRepo() + "/releases/download/"))
  {
    emit kinolelUpdateFehler("Ungültige Update-Adresse");
    return;
  }

  const QString ordner = QStandardPaths::writableLocation(QStandardPaths::TempLocation);
  QDir().mkpath(ordner);
  const QString ziel = QDir(ordner).filePath(QString("%1-Setup-%2.exe").arg(Names::AppName(), version));
  auto* datei = new QFile(ziel, this);
  if (!datei->open(QIODevice::WriteOnly | QIODevice::Truncate))
  {
    emit kinolelUpdateFehler("Datei kann nicht gespeichert werden: " + ziel);
    datei->deleteLater();
    return;
  }

  QNetworkRequest anfrage(quelle);
  anfrage.setHeader(QNetworkRequest::UserAgentHeader, getUserAgent());
  anfrage.setAttribute(QNetworkRequest::RedirectPolicyAttribute, QNetworkRequest::NoLessSafeRedirectPolicy);
  QNetworkReply* antwort = m_networkManager->get(anfrage);

  connect(antwort, &QNetworkReply::readyRead, this, [antwort, datei]() { datei->write(antwort->readAll()); });
  connect(antwort, &QNetworkReply::downloadProgress, this, [this](qint64 empfangen, qint64 gesamt) {
    if (gesamt > 0)
      emit kinolelUpdateFortschritt(static_cast<int>(empfangen * 100 / gesamt));
  });
  connect(antwort, &QNetworkReply::finished, this, [this, antwort, datei, ziel]() {
    antwort->deleteLater();
    datei->write(antwort->readAll());
    datei->close();
    datei->deleteLater();
    QFile pruefung(ziel);
    QByteArray anfang;
    if (pruefung.open(QIODevice::ReadOnly))
      anfang = pruefung.read(2);
    if (antwort->error() != QNetworkReply::NoError || pruefung.size() < 10 * 1024 * 1024 || anfang != "MZ")
    {
      qWarning() << "KinoLel-Update: Download fehlgeschlagen:" << antwort->errorString() << pruefung.size();
      emit kinolelUpdateFehler("Download fehlgeschlagen: " + antwort->errorString());
      return;
    }
    pruefung.close();
    // Still installieren; der Installer schließt KinoLel und startet es danach neu ([Run] mit WizardSilent)
    const QStringList argumente = {"/SILENT", "/SP-", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS"};
    if (!QProcess::startDetached(ziel, argumente))
    {
      emit kinolelUpdateFehler("Installer konnte nicht gestartet werden");
      return;
    }
    qInfo() << "KinoLel-Update: Installer gestartet, beende App";
    QTimer::singleShot(500, qApp, &QCoreApplication::quit);
  });
}

///////////////////////////////////////////////////////////////////////////////////////////////////
// KinoLel (Lel 22.10.2026): „Wenn es ein Update gab, einmalig nach der Aktualisierung eine Meldung, was geändert wurde oder
// neu dazugekommen ist.“ Texte liegen in der App (native/neuigkeiten.json, je Version de/hu/en). Anzeige: native/updatePlugin.js.
// Frisch installiert: nichts. Erste Version mit dieser Meldung nach einem Update: die zwei neuesten Einträge.
// KINOLEL_TEST_NEUIGKEITEN_SEIT=<Version>: nur für den Test im Build (tut so, als sei diese Version zuletzt gesehen).
QVariantList SystemComponent::kinolelNeuigkeiten()
{
  QSettings einstellungen;
  const QVersionNumber aktuell = versionAus(Version::GetVersionString());
  QString gesehenText = einstellungen.value("kinolel/neuigkeitenGesehen").toString();
  if (qEnvironmentVariableIsSet("KINOLEL_TEST_NEUIGKEITEN_SEIT"))
    gesehenText = qEnvironmentVariable("KINOLEL_TEST_NEUIGKEITEN_SEIT");
  const QVersionNumber gesehen = versionAus(gesehenText);
  if (!gesehenText.isEmpty() && QVersionNumber::compare(gesehen, aktuell) >= 0)
    return {};

  // Schon einmal benutzt (Update-Prüfung lief) = Update; sonst frische Installation -> merken, nichts zeigen
  const bool aktualisiert = !gesehenText.isEmpty() || einstellungen.contains("kinolel/updateZuletzt");
  if (!aktualisiert)
  {
    einstellungen.setValue("kinolel/neuigkeitenGesehen", aktuell.toString());
    return {};
  }

  QFile datei(":/web-client/extension/neuigkeiten.json");
  if (!datei.open(QIODevice::ReadOnly))
    return {};
  const QJsonArray versionen = QJsonDocument::fromJson(datei.readAll()).object().value("versionen").toArray();
  QList<QPair<QVersionNumber, QVariantMap>> eintraege;
  for (const QJsonValue& wert : versionen)
  {
    const QJsonObject eintrag = wert.toObject();
    const QVersionNumber v = versionAus(eintrag.value("version").toString());
    if (QVersionNumber::compare(v, aktuell) > 0)
      continue;
    if (!gesehenText.isEmpty() && QVersionNumber::compare(v, gesehen) <= 0)
      continue;
    eintraege.append({v, eintrag.toVariantMap()});
  }
  std::sort(eintraege.begin(), eintraege.end(), [](const auto& a, const auto& b) { return QVersionNumber::compare(a.first, b.first) > 0; });
  if (gesehenText.isEmpty() && eintraege.size() > 2)
    eintraege = eintraege.mid(0, 2);

  QVariantList liste;
  for (const auto& e : eintraege)
    liste.append(e.second);
  qInfo() << "KinoLel-Neuigkeiten:" << liste.size() << "Einträge seit" << (gesehenText.isEmpty() ? QString("?") : gesehenText);
  return liste;
}

///////////////////////////////////////////////////////////////////////////////////////////////////
void SystemComponent::kinolelNeuigkeitenGezeigt()
{
  QSettings einstellungen;
  einstellungen.setValue("kinolel/neuigkeitenGesehen", versionAus(Version::GetVersionString()).toString());
}
