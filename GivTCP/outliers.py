from GivLUT import GivLUT
from settings import GiV_Settings
import pandas as pd
import numpy as np
import os
import datetime
from entity_lut import Entity_Type
logger = GivLUT.logger
givLUT = Entity_Type.entity_type
outliercount=0

def outlier_smoother(x, m=3, win=3, plots=True):
    ''' finds outliers in x, points > m*mdev(x) [mdev:median deviation] 
    and replaces them with the median of win points around them '''
    x_corr = np.copy(x)
    d = np.abs(x - np.median(x))
    mdev = np.median(d)
    idxs_outliers = np.nonzero(d > m*mdev)[0]
    for i in idxs_outliers:
        if i-win < 0:
            x_corr[i] = np.median(np.append(x[0:i], x[i+1:i+win+1]))
        elif i+win+1 > len(x):
            x_corr[i] = np.median(np.append(x[i-win:i], x[i+1:len(x)]))
        else:
            x_corr[i] = np.median(np.append(x[i-win:i], x[i+1:i+win+1]))
#    if plots:
#        plt.figure('outlier_smoother', clear=True)
#        plt.plot(x, label='orig.', lw=5)
#        plt.plot(idxs_outliers, x[idxs_outliers], 'ro', label='outliers')                                                                                                                    
#        plt.plot(x_corr, '-o', label='corrected')
#        plt.legend()
    
    return x_corr

def impute_outliers_IQR(df: np.array, item, nancount: int):
    if GiV_Settings.data_smoother.lower()=="high":
       q1=df.quantile(0.25)
       q3=df.quantile(0.75)
    elif GiV_Settings.data_smoother.lower()=="medium":
       q1=df.quantile(0.15)
       q3=df.quantile(0.85)
    else:
       q1=df.quantile(0.05)
       q3=df.quantile(0.95)
    IQR=q3-q1
    upper = df[~(df>(q3+1.5*IQR))].max()
    lower = df[~(df<(q1-1.5*IQR))].min()
    
    # Expand bounds by 20% of the range to allow values up to 20% outside
    upper_val = upper[0]
    lower_val = lower[0]
    range_val = upper_val - lower_val
    upper_val += 0.2 * range_val
    lower_val -= 0.2 * range_val
    
    # replace outliers with NaN then interpolate
    clean = np.where(df > upper_val,
        np.nan,
        np.where(
            df < lower_val,
            np.nan,
            df
            )
        )
    # iterate clean stack find the dodgy data and log it
    for idx,num in enumerate(clean):
        if np.isnan(num[0]):
            logger.debug(str(item)+" has Outliers: "+str(df.to_dict(orient='list')[0][idx])+" outside bounds: "+str(upper_val)+" - "+str(lower_val))
            nancount+=1
    return [clean,nancount]

def iterate_dict(array):        # Create a publish safe version of the output (convert non string or int datapoints)
    safeoutput = {}
    #dump
    for p_load in array:
        if not p_load=="raw":
            output = array[p_load]
            if isinstance(output, dict):
                temp = iterate_dict(output)
                safeoutput.update(temp)
                #safeoutput[p_load] = output
            else:
                safeoutput[p_load] = output
    return(safeoutput)

def get_outlier_capture_path():
    capture_dir = getattr(GiV_Settings, 'cache_location', '.')
    try:
        os.makedirs(capture_dir, exist_ok=True)
    except OSError:
        pass
    return os.path.join(capture_dir, 'outlier_capture.csv')


def capture_outlier_analysis(flatstack, cleanFlatStack, smoothed_items=None):
    capture_path = get_outlier_capture_path()
    rows = []
    run_ts = datetime.datetime.now().isoformat()
    smoothed_items = smoothed_items or []
    for item, raw_values in flatstack.items():
        if item not in cleanFlatStack or item not in smoothed_items:
            continue
        clean_values = cleanFlatStack[item]
        if len(raw_values) != len(clean_values):
            continue
        for idx, (raw, clean) in enumerate(zip(raw_values, clean_values)):
            try:
                is_outlier = 1 if raw != clean else 0
            except Exception:
                is_outlier = 0
            if is_outlier:  # only capture actual outliers
                rows.append({
                    'timestamp': run_ts,
                    'item': item,
                    'index': idx,
                    'raw': raw,
                    'cleaned': clean,
                    'is_outlier': is_outlier
                })
    if rows:
        df = pd.DataFrame(rows)
        header = not os.path.exists(capture_path)
        df.to_csv(capture_path, mode='a', index=False, header=header)


def makeFlatStack(CacheStack):
    data=[]
    dp=[]
    for cache in CacheStack:
        data.append(iterate_dict(cache))
    flatstack={}
    for cache in data:
        for item in cache:
            if item in flatstack:
                dp=flatstack[item]
                dp.append(cache[item])
                flatstack[item]=dp
            else:
                flatstack[item]=[cache[item]]
    return flatstack

def outlierRemoval(latest_data,CacheStack):
    cleanFlatStack={}
    outliercount=0
    # put latest data into stack
    CacheStack.append(latest_data)

    # get all keys from the stack
    flatstack=makeFlatStack(CacheStack)
    # iterate through a remove outliers
    smoothed_items = []
    for item in flatstack:
        test=flatstack[item][0]
        if givLUT[item].smooth and isinstance(test,(int, float)) and not isinstance(test,bool):
        #if isinstance(test,(int, float)) and not isinstance(test,bool) and not item=="Time_Since_Last_Update":
            df = pd.DataFrame(flatstack[item])
            clean,outliercount=impute_outliers_IQR(df, item,outliercount)
            newdf=pd.DataFrame(clean,dtype=float).interpolate(method='linear',limit_direction='both', limit=10)
            # Fill any remaining NaNs with forward fill to avoid stuck values
            newdf = newdf.ffill()
            # If still NaNs at the beginning, backward fill
            newdf = newdf.bfill()
#            newnewdf=outlier_smoother(df)
            cleanFlatStack[item]=newdf.to_dict(orient='list')[0]
            smoothed_items.append(item)
        else:
            cleanFlatStack[item]=flatstack[item]
    if outliercount > 0:
        logger.info(str(outliercount)+" - outliers found, fixing with interpolated good data")

    # capture the raw vs cleaned values for all smoothed items so plotting can be built later
    try:
        capture_outlier_analysis(flatstack, cleanFlatStack, smoothed_items)
    except Exception as e:
        logger.debug("Failed to write outlier capture: %s" % e)

### NOW put back in the right place...
    for item in cleanFlatStack:
        #find its location in regCache
        outp=list(find(item,CacheStack[0]))
        if not outp == []:
            path=outp[0][1:].split('.')
            for i in range (0, len(CacheStack)-1):  
                try:
                    newdata=cleanFlatStack[item][i]
                    if len(path)==0:
                        CacheStack[i][item]=cleanFlatStack[item][i]
                    elif len(path)==1:
                        CacheStack[i][path[0]][item]=cleanFlatStack[item][i]
                    elif len(path)==2 and not path[1]=="Rates":
                        CacheStack[i][path[0]][path[1]][item]=cleanFlatStack[item][i]
                    elif len(path)==2:
                        CacheStack[i][path[0]][path[1]][item]=cleanFlatStack[item][i]
                    elif len(path)==3:
                        CacheStack[i][path[0]][path[1]][path[2]][item]=cleanFlatStack[item][i]
                except:
                    logger.debug(str(item)+" not in cleanFlat Stack")
    # Put Raw back in

    return CacheStack[-1],CacheStack[:-1]

def find(field_name, d, current_path=''):
    if not isinstance(d, dict):
        return

    if field_name in d:
        yield current_path

    for k in d:
        if isinstance(d[k], list):
            index = 0
            for array_element in d[k]:
                for j in find(field_name, array_element, current_path + f'.{k}.[{index}]'):
                    yield j

                index += 1

        elif isinstance(d[k], dict):
            for found in find(field_name, d[k], current_path + f'.{k}'):
                yield found

def updateitem(obj, key, val):
    if key in obj: 
        obj[key]=123
        return obj
    for k, v in obj.items():
        if isinstance(v,dict):
            item = updateitem(v, key,val)
            if item is not None:
                return obj
    return obj