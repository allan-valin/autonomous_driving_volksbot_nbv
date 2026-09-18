cmake_minimum_required(VERSION 3.8)
project(volksbot_nbv_bringup)

find_package(ament_cmake REQUIRED)

# This package ships configuration and launch files only. Every node it starts
# comes from an upstream package.
install(DIRECTORY launch config
  DESTINATION share/${PROJECT_NAME}
)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  set(ament_cmake_copyright_FOUND TRUE)
  set(ament_cmake_cpplint_FOUND TRUE)
  ament_lint_auto_find_test_dependencies()
endif()

ament_package()
