"""Test data fixtures for FluoroSpot analysis tests."""

import pandas as pd
import numpy as np


def create_basic_test_data():
  """Create basic test data with single donor and simple layout."""
  return pd.DataFrame({
    'Layout-Donor': ['TEST001'] * 12,
    'Plate': ['test_plate_1'] * 12,
    'Layout-Stimuli': ['DMSO'] * 3 + ['PHA'] * 3 + ['LPS'] * 3 + ['Medium'] * 3,
    'Spot Forming Units (SFU)': [5, 8, 6, 45, 52, 48, 35, 40, 38, 2, 3, 1],
    'Analyte Secreting Population': ['LED490 Total'] * 12
  })


def create_multi_cytokine_test_data():
  """Create test data with multiple cytokines."""
  # IFNg data (LED490)
  ifng_data = {
    'Layout-Donor': ['TEST002'] * 8,
    'Plate': ['test_plate_1'] * 8,
    'Layout-Stimuli': ['DMSO', 'DMSO', 'DMSO', 'DMSO', 'PHA', 'PHA', 'PHA', 'PHA'],
    'Spot Forming Units (SFU)': [10, 12, 8, 11, 50, 55, 48, 52],
    'Analyte Secreting Population': ['LED490 Total'] * 8
  }
  
  # IL-10 data (LED550)
  il10_data = {
    'Layout-Donor': ['TEST002'] * 8,
    'Plate': ['test_plate_1'] * 8,
    'Layout-Stimuli': ['DMSO', 'DMSO', 'DMSO', 'DMSO', 'PHA', 'PHA', 'PHA', 'PHA'],
    'Spot Forming Units (SFU)': [15, 18, 12, 16, 75, 80, 70, 78],
    'Analyte Secreting Population': ['LED550 Total'] * 8
  }
  
  df1 = pd.DataFrame(ifng_data)
  df2 = pd.DataFrame(il10_data)
  
  return pd.concat([df1, df2], ignore_index=True)


def create_multi_donor_test_data():
  """Create test data with multiple donors."""
  donors = ['DONOR001', 'DONOR002', 'DONOR003']
  all_data = []
  
  for i, donor in enumerate(donors):
    donor_data = {
      'Layout-Donor': [donor] * 8,
      'Plate': ['test_plate_1'] * 8,
      'Layout-Stimuli': ['DMSO', 'DMSO', 'DMSO', 'DMSO', 'PHA', 'PHA', 'PHA', 'PHA'],
      'Spot Forming Units (SFU)': [
        10 + i, 12 + i, 8 + i, 11 + i, 
        45 + (i * 5), 50 + (i * 5), 48 + (i * 5), 52 + (i * 5)
      ],
      'Analyte Secreting Population': ['LED490 Total'] * 8
    }
    all_data.append(pd.DataFrame(donor_data))
  
  return pd.concat(all_data, ignore_index=True)


def create_experimental_conditions_test_data():
  """Create test data for experimental conditions mode."""
  return pd.DataFrame({
    'Layout-Donor': ['EXP001'] * 16,
    'Plate': ['exp_plate_1'] * 16,
    'Layout-Stimuli': [
      'DMSO_G1', 'DMSO_G1', 'DMSO_G1', 'DMSO_G1',  # Group 1 control
      'STIM_G1_A', 'STIM_G1_A', 'STIM_G1_B', 'STIM_G1_B',  # Group 1 stimuli
      'DMSO_G2', 'DMSO_G2', 'DMSO_G2', 'DMSO_G2',  # Group 2 control
      'STIM_G2_A', 'STIM_G2_A', 'STIM_G2_B', 'STIM_G2_B'   # Group 2 stimuli
    ],
    'Spot Forming Units (SFU)': [
      8, 10, 9, 11,  # Group 1 control
      40, 45, 35, 38,  # Group 1 stimuli
      12, 14, 13, 15,  # Group 2 control
      60, 65, 55, 58   # Group 2 stimuli
    ],
    'Analyte Secreting Population': ['LED490 Total'] * 16
  })


def create_edge_case_test_data():
  """Create test data with edge cases (NaN values, zeros, etc.)."""
  return pd.DataFrame({
    'Layout-Donor': ['EDGE001'] * 12,
    'Plate': ['edge_plate_1'] * 12,
    'Layout-Stimuli': ['DMSO'] * 4 + ['STIM_HIGH'] * 4 + ['STIM_LOW'] * 4,
    'Spot Forming Units (SFU)': [
      10, 12, np.nan, 11,  # Control with NaN
      150, 200, 180, 175,  # Very high response
      0, 1, 0, 2           # Very low/zero response
    ],
    'Analyte Secreting Population': ['LED490 Total'] * 12
  })


def create_no_response_test_data():
  """Create test data where stimuli don't show significant response."""
  return pd.DataFrame({
    'Layout-Donor': ['NORESPONSE001'] * 8,
    'Plate': ['no_resp_plate_1'] * 8,
    'Layout-Stimuli': ['DMSO', 'DMSO', 'DMSO', 'DMSO', 'WEAK_STIM', 'WEAK_STIM', 'WEAK_STIM', 'WEAK_STIM'],
    'Spot Forming Units (SFU)': [10, 12, 8, 11, 12, 14, 9, 13],  # Similar values for control and stim
    'Analyte Secreting Population': ['LED490 Total'] * 8
  })


def create_numerical_stimuli_test_data():
  """Create test data with numerical stimuli names."""
  return pd.DataFrame({
    'Layout-Donor': ['NUMERICAL001'] * 12,
    'Plate': ['numerical_plate_1'] * 12,
    'Layout-Stimuli': ['DMSO', 'DMSO', 'DMSO', 'DMSO', 4990.67, 4990.67, 4990.67, 4990.67, 1234, 1234, 1234, 1234],
    'Spot Forming Units (SFU)': [8, 10, 9, 11, 50, 55, 48, 52, 35, 40, 38, 42],
    'Analyte Secreting Population': ['LED490 Total'] * 12
  })


def create_multi_donor_single_plate_test_data():
  """Create test data with multiple donors in a single plate file."""
  # Donor 1 data
  donor1_data = {
    'Layout-Donor': ['DONOR_A'] * 8,
    'Plate': ['plate_1'] * 8,
    'Layout-Stimuli': ['DMSO', 'DMSO', 'DMSO', 'DMSO', 'PHA', 'PHA', 'PHA', 'PHA'],
    'Spot Forming Units (SFU)': [10, 12, 8, 11, 50, 55, 48, 52],
    'Analyte Secreting Population': ['LED490 Total'] * 8
  }
  
  # Donor 2 data
  donor2_data = {
    'Layout-Donor': ['DONOR_B'] * 8,
    'Plate': ['plate_1'] * 8,
    'Layout-Stimuli': ['DMSO', 'DMSO', 'DMSO', 'DMSO', 'PHA', 'PHA', 'PHA', 'PHA'],
    'Spot Forming Units (SFU)': [15, 18, 12, 16, 75, 80, 70, 78],
    'Analyte Secreting Population': ['LED490 Total'] * 8
  }
  
  df1 = pd.DataFrame(donor1_data)
  df2 = pd.DataFrame(donor2_data)
  
  return pd.concat([df1, df2], ignore_index=True)


if __name__ == '__main__':
  # Example usage
  print("Basic test data:")
  print(create_basic_test_data().head())
  
  print("\nMulti-cytokine test data:")
  print(create_multi_cytokine_test_data().head())
  
  print("\nMulti-donor test data:")
  print(create_multi_donor_test_data().head())