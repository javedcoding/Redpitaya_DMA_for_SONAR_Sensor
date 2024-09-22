import numpy as np
import math
from scipy.signal import stft



def get_arrays_with_overlap_percent(original_array, overlap_percentage=50, single_segment_size=100):
    len_of_org_array = len(original_array)
    overlap_size = overlap_percentage * single_segment_size / 100
    range_of_overlap_array = math.ceil((len_of_org_array - overlap_size) / (single_segment_size - overlap_size))
    overlapped_arrays = list()
    start_index = 0
    for i in range(range_of_overlap_array):
        overlapped_arrays.append(np.array(original_array[start_index:start_index + single_segment_size]))
        start_index = int(start_index +  ((100 - overlap_percentage)* single_segment_size)/100)
    return np.array(overlapped_arrays[:-1])

def hamming_window(length):
    return 0.54 - 0.46 * np.cos(2 * np.pi * np.arange(length) / (length - 1))

def get_stft_of_signal(sig_to_stft, fs=1953125, nperseg=100, noverlap=50):
    freq_sig, t_sig, spectrogram_sig = stft(sig_to_stft, fs=fs, nperseg=nperseg, noverlap=noverlap)
    return spectrogram_sig

def stft_of_complete_raw_adc(raw_adc_data, start_index, end_index):
    print(start_index, end_index, "++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
    start_index = math.floor(start_index)
    end_index = math.floor(end_index)

    first_empty_arrays = get_arrays_with_overlap_percent(raw_adc_data[:start_index])
    mid_return_arrays = get_arrays_with_overlap_percent(raw_adc_data[start_index:end_index])
    last_empty_arrays = get_arrays_with_overlap_percent(raw_adc_data[end_index:])
    single_segment_size = 100
    hamming_window_for_seg_signal = hamming_window(single_segment_size)

    # Elementwise multiplication of the segmented signal to get hammed signal
    hammed_first_empty_arrays = np.multiply(first_empty_arrays, hamming_window_for_seg_signal)
    hammed_mid_return_arrays = np.multiply(mid_return_arrays, hamming_window_for_seg_signal)
    hammed_last_empty_arrays = np.multiply(last_empty_arrays, hamming_window_for_seg_signal)


    # STFT of Hammed Array
    stft_first_empty_arrays = np.apply_along_axis(get_stft_of_signal, axis=1, arr=hammed_first_empty_arrays)
    stft_mid_return_arrays = np.apply_along_axis(get_stft_of_signal, axis=1, arr=hammed_mid_return_arrays)
    stft_last_empty_arrays = np.apply_along_axis(get_stft_of_signal, axis=1, arr=hammed_last_empty_arrays)

    print(stft_first_empty_arrays.shape, stft_mid_return_arrays.shape, stft_last_empty_arrays.shape)
