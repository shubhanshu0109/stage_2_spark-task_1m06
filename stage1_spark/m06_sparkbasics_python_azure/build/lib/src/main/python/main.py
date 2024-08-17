from pyspark.sql import SparkSession
from pyspark.sql.functions import udf, struct, avg, lit, round, col, when
import requests
from pyspark.sql.types import DoubleType, StructField, FloatType, StringType, StructType
from dotenv import load_dotenv
import os
import logging
import geohash2

load_dotenv()

# Initialize logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Function to get coordinates from OpenCage API
# This function takes an address, city, and country as input, constructs a full address,
# sends a request to the OpenCage API, and returns the latitude and longitude of the address.
def get_coordinates(address, city, country):
    try:
        full_address = f"{address}, {city}, {country}"
        key = os.getenv('OPENCAGE_API_KEY')
        api_url = f"https://api.opencagedata.com/geocode/v1/json?q={full_address}&{key}"
        response = requests.get(api_url)
        data = response.json()
        if data["results"]:
            return (data["results"][0]["geometry"]["lat"], data["results"][0]["geometry"]["lng"])
        else:
            return (None, None)
    except Exception as e:
        logger.error(f"Failed to get coordinates for address {full_address}: {e}")
        return (None, None)

# Function to get geohash
def get_geohash(latitude, longitude):
    return geohash2.encode(latitude, longitude, precision=4)

if __name__ == '__main__':
    # Define storage account name, key and container name

    storage_account_name =  os.getenv('STORAGE_ACCOUNT_NAME')
    key = os.getenv('API_KEY')
    container_name = os.getenv('CONTAINER_NAME')

    # Initialize SparkSession with necessary configurations
    # This is the entry point to any functionality in Spark.
    spark = SparkSession \
        .builder \
        .appName("Python Spark SQL basic example") \
        .config('spark.jars.packages',
                'org.apache.hadoop:hadoop-azure:3.3.1,'
                'org.apache.hadoop:hadoop-azure-datalake:3.3.1,'
                'com.microsoft.azure:azure-storage:7.0.0,'
                'com.microsoft.azure:azure-data-lake-store-sdk:2.3.6') \
        .config(f"spark.hadoop.fs.azure.account.key.{storage_account_name}.blob.core.windows.net", key) \
        .config("spark.network.timeout", "800s") \
        .getOrCreate()

    # Read hotels data from Azure in CSV format
    hotel_df = spark.read.csv(f"wasbs://{container_name}@{storage_account_name}.blob.core.windows.net/m06sparkbasics/hotels/part-00003-7b2b2c30-eb5e-4ab6-af89-28fae7bdb9e4-c000.csv.gz", header=True)

    # Read weather data from Azure in Parquet format
    weather_df = spark.read.parquet(
        f"wasbs://{container_name}@{storage_account_name}.blob.core.windows.net/m06sparkbasics/weather/year=2016/month=10/day=01/part-00141-44bd3411-fbe4-4e16-b667-7ec0fc3ad489.c000.snappy.parquet")

    # Filter out rows where Latitude and Longitude are NULL or NA
    hotel_df_with_missing_coordinates = hotel_df.filter((col('Latitude').isNull()) | (col('Latitude') == 'NA') | (col('Longitude').isNull() | (col('Longitude') == 'NA')))

    # Define schema for latitude and longitude
    schema = StructType([
        StructField("Latitude", DoubleType(), True),
        StructField("Longitude", DoubleType(), True)
    ])

    # Define UDF for get_coordinates function
    get_coordinates_udf = udf(get_coordinates, schema)

    # Add new column "Coordinates" to df_null with values from API
    hotel_df_with_missing_coordinates = hotel_df_with_missing_coordinates.withColumn("Coordinates", get_coordinates_udf(col("Address"), col("City"), col("Country")))
    hotel_df_with_missing_coordinates = hotel_df_with_missing_coordinates.withColumn("Latitude_new", col("Coordinates.Latitude"))
    hotel_df_with_missing_coordinates = hotel_df_with_missing_coordinates.withColumn("Longitude_new", col("Coordinates.Longitude"))
    hotel_df_with_missing_coordinates = hotel_df_with_missing_coordinates.drop("Coordinates")

    hotel_df_with_missing_coordinates.show()

    # Join original DataFrame with df_null on Id
    hotel_new = hotel_df.join(hotel_df_with_missing_coordinates.select("Id", "Latitude_new", "Longitude_new"), on="Id", how="left")

    # Update original latitude and longitude columns with new values
    hotel_new = hotel_new.withColumn("Latitude",
                                     when((col("Latitude").isNull()) | (col("Latitude") == ""),
                                          col("Latitude_new")).otherwise(col("Latitude"))) \
        .withColumn("Longitude",
                    when((col("Longitude").isNull()) | (col("Longitude") == ""), col("Longitude_new")).otherwise(
                        col("Longitude"))) \
        .drop("Latitude_new", "Longitude_new")

    # Drop original latitude and longitude columns from df_null
    # This removes the original latitude and longitude columns from the DataFrame that contains the new coordinates.
    hotel_df_with_missing_coordinates = hotel_df_with_missing_coordinates.drop('Latitude').drop('Longitude')
    # Rename column "old_name" to "new_name"
    # This renames the columns that contain the new coordinates to the original names.
    hotel_df_with_missing_coordinates = hotel_df_with_missing_coordinates.withColumnRenamed("Latitude_new", "Latitude").withColumnRenamed(
        "Longitude_new", "Longitude")

    # Define UDF for get_geohash function
    get_geohash_udf = udf(get_geohash, StringType())

    # Generate a geohash from the 'Latitude' and 'Longitude' columns
    # This calls the get_geohash function for each row in the DataFrame and adds the returned geohash as a new column.
    hotel_new = hotel_new.withColumn("Latitude", col("Latitude").cast(FloatType()))
    hotel_new = hotel_new.withColumn("Longitude", col("Longitude").cast(FloatType()))
    hotel_new = hotel_new.filter(col("Latitude").isNotNull() & col("Longitude").isNotNull())
    hotel_new = hotel_new.withColumn("Geohash", get_geohash_udf(col("Latitude"), col("Longitude")))

    # Generate a geohash for weather data
    # This calls the get_geohash function for each row in the weather DataFrame and adds the returned geohash as a new column.
    weather_df = weather_df.withColumn("Geohash", get_geohash_udf(col("lat"), col("lng")))

    # Group weather data by 'wthr_date' and 'Geohash' and calculate average temperature
    # This groups the weather data by date and geohash, calculates the average temperature for each group, and creates a new DataFrame with these values.
    weather_df = weather_df.groupBy('wthr_date', 'Geohash') \
        .agg(round(avg('avg_tmpr_f'), 2).alias('avg_tmpr_f'),
             round(avg('avg_tmpr_c'), 2).alias('avg_tmpr_c')).dropDuplicates()

    # Join hotel and weather data on 'Geohash'
    # This merges the hotel and weather DataFrames based on the geohash column.
    merged_df = hotel_new.join(weather_df, on='Geohash', how='left')
    merged_df.show()

    # target_container = 'sparkoutput'
    # folder = 'result'
    #
    # output_path = f"wasbs://{target_container}@{storage_account_name}.blob.core.windows.net/{folder}"
    # merged_df.write.mode("overwrite").csv(output_path)