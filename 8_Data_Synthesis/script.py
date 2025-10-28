import pandas as pd

# Name of your Excel file (same folder as this script)
file_name = "Data_Extraction.xlsx"

# Read the Excel file
df = pd.read_excel(file_name)

# Select the columns you need by Excel letters
# (convert letters to 0-based indices: A=0 → E=4, Z=25, AA=26, AB=27, AD=29, AG=32)
cols = [4, 25, 26, 27, 28, 29, 32]
selected = df.iloc[:, cols]

# Iterate over rows and print values separated by %%
for _, row in selected.iterrows():
    # Convert all to string and join with %%
    line = " %% ".join(str(x) for x in row)
    print(line)
