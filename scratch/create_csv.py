import pandas as pd

df = pd.DataFrame(columns=['username', 'name', 'email', 'phone_number', 'password', 'upload_dir', 'ai_upload_dir', 'past_upload_dir', 'subscription', 'remaining_photos'])

df.to_csv("customers_info.csv", index=False)