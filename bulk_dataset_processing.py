import df2tables as df2t
from vega_datasets import data

# WARNING: This will open many browser tabs! Use with caution.
# Consider setting startfile=False for bulk processing.

for dataset_name in sorted(dir(data))[:10]:
    dataset_func = getattr(data, dataset_name)
    try:
        df = dataset_func()
        print(f"{dataset_name}: {len(df.index)} rows")
        
        # df2tables can handle datasets above 100k rows, but we limit to smaller datasets 
        # for this demo to avoid generating too many large files
        if len(df.index) < 100_000:
            df2t.render(
                df, 
                title=f'Dataset: {dataset_name}',
                to_file=f'{dataset_name}.html',
                startfile=True  
            )
    except Exception as e:
        print(f'Error processing {dataset_name}: {e}')