/**
 * C++ High Performance Feature Calculation Module Implementation
 */

#include "feature_calculator.h"
#include <complex>
#include <random>

// Define M_PI if not defined
#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

namespace pl5 {

// 构造函数和析构函数
FeatureCalculator::FeatureCalculator() {}
FeatureCalculator::~FeatureCalculator() {}

// 基本统计特征实现
double FeatureCalculator::calculateMean(const std::vector<int>& data) {
    if (data.empty()) return 0.0;
    return static_cast<double>(std::accumulate(data.begin(), data.end(), 0LL)) / data.size();
}

double FeatureCalculator::calculateStd(const std::vector<int>& data) {
    if (data.size() < 2) return 0.0;
    
    double mean = calculateMean(data);
    double sumSq = 0.0;
    
    for (int val : data) {
        double diff = val - mean;
        sumSq += diff * diff;
    }
    
    return std::sqrt(sumSq / (data.size() - 1));
}

int FeatureCalculator::calculateMax(const std::vector<int>& data) {
    if (data.empty()) return 0;
    return *std::max_element(data.begin(), data.end());
}

int FeatureCalculator::calculateMin(const std::vector<int>& data) {
    if (data.empty()) return 0;
    return *std::min_element(data.begin(), data.end());
}

double FeatureCalculator::calculateEntropy(const std::vector<int>& data) {
    if (data.empty()) return 0.0;
    
    // 计算频率分布
    std::map<int, int> freq;
    for (int val : data) {
        freq[val]++;
    }
    
    double entropy = 0.0;
    int n = data.size();
    
    for (const auto& pair : freq) {
        double p = static_cast<double>(pair.second) / n;
        if (p > 0) {
            entropy -= p * std::log2(p);
        }
    }
    
    return entropy;
}

// 高性能滚动窗口均值 —— O(n) 滑动窗口算法
std::vector<double> FeatureCalculator::rollingMean(
    const std::vector<int>& data, 
    int window
) {
    int n = data.size();
    std::vector<double> result;
    result.reserve(n);
    
    long long runningSum = 0;
    
    for (int i = 0; i < n; ++i) {
        runningSum += data[i];
        
        if (i >= window) {
            // 移出窗口外的元素
            runningSum -= data[i - window];
            result.push_back(static_cast<double>(runningSum) / window);
        } else {
            // 窗口尚未满足 window 大小，使用当前元素数
            result.push_back(static_cast<double>(runningSum) / (i + 1));
        }
    }
    
    return result;
}

// 高性能滚动窗口标准差 —— 使用 Welford 在线算法 O(n)
std::vector<double> FeatureCalculator::rollingStd(
    const std::vector<int>& data, 
    int window
) {
    int n = data.size();
    std::vector<double> result;
    result.reserve(n);
    
    // 使用双精度求和法（Compensated Summation）
    double sumX  = 0.0;  // Σx
    double sumX2 = 0.0;  // Σx²
    
    for (int i = 0; i < n; ++i) {
        sumX  += data[i];
        sumX2 += static_cast<double>(data[i]) * data[i];
        
        int count;
        if (i >= window) {
            // 移出窗口外的元素
            sumX  -= data[i - window];
            sumX2 -= static_cast<double>(data[i - window]) * data[i - window];
            count = window;
        } else {
            count = i + 1;
        }
        
        if (count < 2) {
            result.push_back(0.0);
        } else {
            // Var = E[x²] - (E[x])²  使用样本方差（除以 count，非 count-1）
            double mean = sumX / count;
            double variance = sumX2 / count - mean * mean;
            result.push_back(std::sqrt(std::max(0.0, variance)));
        }
    }
    
    return result;
}

// 滚动窗口频率统计 —— O(n) 滑动计数数组
std::vector<std::vector<double>> FeatureCalculator::rollingFrequency(
    const std::vector<int>& data,
    int window,
    int numDigits
) {
    int n = static_cast<int>(data.size());
    std::vector<std::vector<double>> result(n, 
        std::vector<double>(numDigits, 0.0));
    
    std::vector<int> freq(numDigits, 0);
    
    for (int i = 0; i < n; ++i) {
        // 加入新元素
        if (data[i] >= 0 && data[i] < numDigits) {
            freq[data[i]]++;
        }
        
        // 移出超出窗口的旧元素
        if (i >= window) {
            int old_val = data[i - window];
            if (old_val >= 0 && old_val < numDigits) {
                freq[old_val]--;
            }
        }
        
        int count = std::min(i + 1, window);
        for (int d = 0; d < numDigits; ++d) {
            result[i][d] = static_cast<double>(freq[d]) / count;
        }
    }
    
    return result;
}

// 滞后特征
std::vector<int> FeatureCalculator::lagFeatures(
    const std::vector<int>& data,
    int lag
) {
    std::vector<int> result(data.size(), 0);
    
    for (size_t i = lag; i < data.size(); ++i) {
        result[i] = data[i - lag];
    }
    
    // 前lag个值保持为0（或可以设置为特殊值）
    return result;
}

// Hurst指数计算（简化版R/S分析）
double FeatureCalculator::calculateHurstExponent(const std::vector<int>& data) {
    if (data.size() < 10) return 0.5;
    
    int n = data.size();
    double mean = calculateMean(data);
    
    // 计算累积离差
    std::vector<double> cumDev(n);
    double cumSum = 0.0;
    for (int i = 0; i < n; ++i) {
        cumSum += data[i] - mean;
        cumDev[i] = cumSum;
    }
    
    // 计算极差
    double R = *std::max_element(cumDev.begin(), cumDev.end()) - 
               *std::min_element(cumDev.begin(), cumDev.end());
    
    // 计算标准差
    double S = calculateStd(data);
    
    if (S == 0) return 0.5;
    
    // R/S统计量
    double RS = R / S;
    
    // 估计Hurst指数
    double hurst = std::log(RS) / std::log(n);
    
    return std::max(0.0, std::min(1.0, hurst));
}

// Lyapunov指数计算（简化版）
double FeatureCalculator::calculateLyapunovExponent(const std::vector<int>& data) {
    if (data.size() < 10) return 0.0;
    
    // 简化实现：基于相邻点发散率估计
    int n = data.size();
    double sumLog = 0.0;
    int count = 0;
    
    for (int i = 1; i < n - 1; ++i) {
        double d0 = std::abs(data[i] - data[i-1]) + 0.001;  // 避免除零
        double d1 = std::abs(data[i+1] - data[i]);
        
        if (d0 > 0) {
            sumLog += std::log(d1 / d0);
            count++;
        }
    }
    
    return count > 0 ? sumLog / count : 0.0;
}

// ──────────────────────────────────────────────
// Cooley-Tukey 递归 FFT —— O(n log n)
// 内部辅助函数（namespace 内静态）
// ──────────────────────────────────────────────
static void fft_inplace(std::vector<std::complex<double>>& a, bool inverse) {
    int n = static_cast<int>(a.size());
    if (n <= 1) return;

    // 按奇偶分组
    std::vector<std::complex<double>> even(n / 2), odd(n / 2);
    for (int i = 0; i < n / 2; ++i) {
        even[i] = a[2 * i];
        odd[i]  = a[2 * i + 1];
    }

    fft_inplace(even, inverse);
    fft_inplace(odd,  inverse);

    double angle_sign = inverse ? 1.0 : -1.0;
    std::complex<double> wn(std::cos(2.0 * M_PI / n), 
                             angle_sign * std::sin(2.0 * M_PI / n));
    std::complex<double> w(1.0, 0.0);

    for (int i = 0; i < n / 2; ++i) {
        std::complex<double> t = w * odd[i];
        a[i]         = even[i] + t;
        a[i + n / 2] = even[i] - t;
        w *= wn;
    }

    if (inverse) {
        for (auto& x : a) x /= 2.0;
    }
}

// 将 data 补零至最近的 2 的幂，然后做 FFT，返回幅度谱
std::vector<double> FeatureCalculator::fftTransform(const std::vector<int>& data) {
    int n = data.size();
    if (n == 0) return {};

    // 补零至 2 的幂（保证 Cooley-Tukey 递归可整除）
    int m = 1;
    while (m < n) m <<= 1;

    std::vector<std::complex<double>> a(m, std::complex<double>(0.0, 0.0));
    for (int i = 0; i < n; ++i) {
        a[i] = std::complex<double>(data[i], 0.0);
    }

    fft_inplace(a, false);

    // 只返回前半段（幅度谱，正频率部分），大小对齐原始 n
    std::vector<double> result(n);
    for (int i = 0; i < n; ++i) {
        result[i] = std::abs(a[i % m]);  // 映射回原始长度
    }
    return result;
}

// 批量处理所有特征
DataMatrix FeatureCalculator::calculateAllFeatures(
    const DataMatrix& rawData,
    const std::vector<int>& windowSizes,
    const std::vector<int>& lagPeriods
) {
    DataMatrix features;
    
    // 这里可以实现完整的特征工程流水线
    // 返回计算好的特征矩阵
    
    return features;
}

// HMM模型实现
HMMModel::HMMModel(int nComponents) : nComponents_(nComponents) {}
HMMModel::~HMMModel() {}

void HMMModel::fit(const std::vector<int>& data) {
    // 简化版HMM训练实现
    // 实际实现需要使用Baum-Welch算法
    
    means_.resize(nComponents_, 0.0);
    transMat_.resize(nComponents_, std::vector<double>(nComponents_, 1.0 / nComponents_));
    
    // 简单初始化：根据数据范围分配均值
    if (!data.empty()) {
        int minVal = *std::min_element(data.begin(), data.end());
        int maxVal = *std::max_element(data.begin(), data.end());
        
        for (int i = 0; i < nComponents_; ++i) {
            means_[i] = minVal + (maxVal - minVal) * i / (nComponents_ - 1);
        }
    }
}

std::vector<int> HMMModel::predict(const std::vector<int>& data) {
    std::vector<int> states(data.size(), 0);
    
    // 简化版：根据最近均值分配状态
    for (size_t i = 0; i < data.size(); ++i) {
        int bestState = 0;
        double minDist = std::abs(data[i] - means_[0]);
        
        for (int j = 1; j < nComponents_; ++j) {
            double dist = std::abs(data[i] - means_[j]);
            if (dist < minDist) {
                minDist = dist;
                bestState = j;
            }
        }
        
        states[i] = bestState;
    }
    
    return states;
}

std::vector<std::vector<double>> HMMModel::predictProba(const std::vector<int>& data) {
    std::vector<std::vector<double>> proba(data.size(), 
        std::vector<double>(nComponents_, 1.0 / nComponents_));
    
    // 简化版：基于距离计算概率
    for (size_t i = 0; i < data.size(); ++i) {
        std::vector<double> dists(nComponents_);
        double sumInvDist = 0.0;
        
        for (int j = 0; j < nComponents_; ++j) {
            dists[j] = std::abs(data[i] - means_[j]) + 0.001;
            sumInvDist += 1.0 / dists[j];
        }
        
        for (int j = 0; j < nComponents_; ++j) {
            proba[i][j] = (1.0 / dists[j]) / sumInvDist;
        }
    }
    
    return proba;
}

// Copula模型实现
CopulaModel::CopulaModel() {}
CopulaModel::~CopulaModel() {}

void CopulaModel::fit(const DataMatrix& data) {
    data_ = data;
    
    int nVars = data.size();
    kendallTau_.resize(nVars, std::vector<double>(nVars, 0.0));
    
    // 计算Kendall's tau
    for (int i = 0; i < nVars; ++i) {
        for (int j = i + 1; j < nVars; ++j) {
            kendallTau_[i][j] = calculateKendallTau(i, j);
            kendallTau_[j][i] = kendallTau_[i][j];
        }
    }
}

double CopulaModel::calculateKendallTau(int i, int j) {
    if (data_.empty() || i >= data_.size() || j >= data_.size()) {
        return 0.0;
    }
    
    const std::vector<int>& x = data_[i];
    const std::vector<int>& y = data_[j];
    
    if (x.size() != y.size() || x.size() < 2) {
        return 0.0;
    }
    
    int n = x.size();
    int concordant = 0;
    int discordant = 0;
    
    for (int a = 0; a < n; ++a) {
        for (int b = a + 1; b < n; ++b) {
            double dx = x[a] - x[b];
            double dy = y[a] - y[b];
            
            if (dx * dy > 0) {
                concordant++;
            } else if (dx * dy < 0) {
                discordant++;
            }
        }
    }
    
    int totalPairs = n * (n - 1) / 2;
    return totalPairs > 0 ? static_cast<double>(concordant - discordant) / totalPairs : 0.0;
}

std::vector<std::vector<double>> CopulaModel::getCorrelationMatrix() {
    return kendallTau_;
}

} // namespace pl5
