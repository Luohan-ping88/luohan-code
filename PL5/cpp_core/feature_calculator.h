/**
 * C++ High Performance Feature Calculation Module
 * For accelerating feature engineering calculations in Python
 */

#ifndef FEATURE_CALCULATOR_H
#define FEATURE_CALCULATOR_H

#include <vector>
#include <string>
#include <map>
#include <cmath>
#include <numeric>
#include <algorithm>

namespace pl5 {

// Define data types
using DataMatrix = std::vector<std::vector<int>>;
using FeatureVector = std::vector<double>;

/**
 * High Performance Feature Calculator Class
 */
class FeatureCalculator {
public:
    FeatureCalculator();
    ~FeatureCalculator();

    // Basic statistical features
    static double calculateMean(const std::vector<int>& data);
    static double calculateStd(const std::vector<int>& data);
    static int calculateMax(const std::vector<int>& data);
    static int calculateMin(const std::vector<int>& data);
    static double calculateEntropy(const std::vector<int>& data);
    
    // Rolling window features (high performance implementation)
    static std::vector<double> rollingMean(
        const std::vector<int>& data, 
        int window
    );
    
    static std::vector<double> rollingStd(
        const std::vector<int>& data, 
        int window
    );
    
    static std::vector<std::vector<double>> rollingFrequency(
        const std::vector<int>& data,
        int window,
        int numDigits = 10
    );
    
    // Lag features
    static std::vector<int> lagFeatures(
        const std::vector<int>& data,
        int lag
    );
    
    // High-order features
    static double calculateHurstExponent(const std::vector<int>& data);
    static double calculateLyapunovExponent(const std::vector<int>& data);
    static std::vector<double> fftTransform(const std::vector<int>& data);
    
    // Batch processing interface
    static DataMatrix calculateAllFeatures(
        const DataMatrix& rawData,
        const std::vector<int>& windowSizes,
        const std::vector<int>& lagPeriods
    );
};

/**
 * High Performance HMM Model Implementation
 */
class HMMModel {
public:
    HMMModel(int nComponents = 4);
    ~HMMModel();
    
    void fit(const std::vector<int>& data);
    std::vector<int> predict(const std::vector<int>& data);
    std::vector<std::vector<double>> predictProba(const std::vector<int>& data);
    
private:
    int nComponents_;
    std::vector<double> means_;
    std::vector<std::vector<double>> transMat_;
};

/**
 * High Performance Copula Model Implementation
 */
class CopulaModel {
public:
    CopulaModel();
    ~CopulaModel();
    
    void fit(const DataMatrix& data);
    double calculateKendallTau(int i, int j);
    std::vector<std::vector<double>> getCorrelationMatrix();
    
private:
    DataMatrix data_;
    std::vector<std::vector<double>> kendallTau_;
};

} // namespace pl5

#endif // FEATURE_CALCULATOR_H
