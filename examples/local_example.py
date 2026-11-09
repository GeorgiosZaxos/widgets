import time

# from widgets import tqdm
#
# for i in tqdm(range(100), spinner="dots", gradient=["#ff3b30", "#ffcc00", "#34c759"]):
#     time.sleep(0.03)
from widgets import vtqdm

for _i in vtqdm(range(100), spinner="dots", gradient=["#ff3b30", "#ffcc00", "#34c759"]):
    time.sleep(0.03)
