/**
 * Python binding - using pybind11
 */

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/numpy.h>
#include <chrono>
#include "feature_calculator.h"

namespace py = pybind11;
using namespace pl5;

PYBIND11_MODULE(pl5_core, m) {
    m.doc() = "PL5 High Performance Computing Core Module";

    // FeatureCalculator class binding
    py::class_<FeatureCalculator>(m, "FeatureCalculator")
        .def(py::init<>())
        .def_static("calculate_mean", &FeatureCalculator::calculateMean,
                   "Calculate mean value", py::arg("data"))
        .def_static("calculate_std", &FeatureCalculator::calculateStd,
                   "Calculate standard deviation", py::arg("data"))
        .def_static("calculate_max", &FeatureCalculator::calculateMax,
                   "Calculate maximum value", py::arg("data"))
        .def_static("calculate_min", &FeatureCalculator::calculateMin,
                   "Calculate minimum value", py::arg("data"))
        .def_static("calculate_entropy", &FeatureCalculator::calculateEntropy,
                   "Calculate entropy", py::arg("data"))
        .def_static("rolling_mean", &FeatureCalculator::rollingMean,
                   "Rolling window mean", py::arg("data"), py::arg("window"))
        .def_static("rolling_std", &FeatureCalculator::rollingStd,
                   "Rolling window standard deviation", py::arg("data"), py::arg("window"))
        .def_static("rolling_frequency", &FeatureCalculator::rollingFrequency,
                   "Rolling window frequency", py::arg("data"), py::arg("window"), py::arg("num_digits") = 10)
        .def_static("lag_features", &FeatureCalculator::lagFeatures,
                   "Lag features", py::arg("data"), py::arg("lag"))
        .def_static("calculate_hurst", &FeatureCalculator::calculateHurstExponent,
                   "Calculate Hurst exponent", py::arg("data"))
        .def_static("calculate_lyapunov", &FeatureCalculator::calculateLyapunovExponent,
                   "Calculate Lyapunov exponent", py::arg("data"))
        .def_static("fft_transform", &FeatureCalculator::fftTransform,
                   "FFT transform", py::arg("data"));

    // HMMModel class binding
    py::class_<HMMModel>(m, "HMMModel")
        .def(py::init<int>(), "Constructor", py::arg("n_components") = 4)
        .def("fit", &HMMModel::fit, "Train model", py::arg("data"))
        .def("predict", &HMMModel::predict, "Predict state", py::arg("data"))
        .def("predict_proba", &HMMModel::predictProba, "Predict state probability", py::arg("data"));

    // CopulaModel class binding
    py::class_<CopulaModel>(m, "CopulaModel")
        .def(py::init<>())
        .def("fit", &CopulaModel::fit, "Train model", py::arg("data"))
        .def("calculate_kendall_tau", &CopulaModel::calculateKendallTau,
             "Calculate Kendall's tau", py::arg("i"), py::arg("j"))
        .def("get_correlation_matrix", &CopulaModel::getCorrelationMatrix,
             "Get correlation matrix");

    // Benchmark function
    m.def("benchmark", []() {
        // Simple performance test
        std::vector<int> test_data(10000);
        for (int i = 0; i < 10000; ++i) {
            test_data[i] = i % 10;
        }

        auto start = std::chrono::high_resolution_clock::now();

        // Execute calculations
        for (int i = 0; i < 1000; ++i) {
            FeatureCalculator::rollingMean(test_data, 20);
        }

        auto end = std::chrono::high_resolution_clock::now();
        auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(end - start);

        return duration.count();
    }, "Performance benchmark");
}
