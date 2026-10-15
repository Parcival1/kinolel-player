# KinoLel: Name, Server usw. kommen aus marke.cmake (einzige Stelle)
include(${CMAKE_SOURCE_DIR}/marke.cmake)

set(MAIN_TARGET JellyfinDesktop)

# Output binary name
string(TOLOWER "${APP_NAME}" APP_NAME_LOWER)
set(MAIN_NAME ${APP_NAME_LOWER})

# Data directory name - also used for QCoreApplication::applicationName
# which determines QStandardPaths (cache, config, data dirs)
set(DATA_NAME ${APP_NAME_LOWER})

if(APPLE)
  set(MAIN_NAME "${APP_NAME}")
  set(DATA_NAME "${APP_NAME}")
elseif(WIN32)
  set(MAIN_NAME "${APP_NAME}")
  set(DATA_NAME "${APP_NAME}")
endif()

configure_file(src/shared/Names.cpp.in src/shared/Names.cpp @ONLY)
