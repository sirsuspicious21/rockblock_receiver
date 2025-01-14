import binascii
import json
from django.http import JsonResponse
from django.shortcuts import render
from rest_framework.decorators import api_view

from receiver.decompression import process_compressed_data
from .models import RockBlockMessage
from django.core import serializers
import numpy as np


@api_view(["POST"])
def receive_message(request):
    if request.method == 'POST':
        imei = request.POST.get('imei')
        momsn = request.POST.get('momsn')
        transmit_time = request.POST.get('transmit_time')
        iridium_latitude = request.POST.get('iridium_latitude')
        iridium_longitude = request.POST.get('iridium_longitude')
        iridium_cep = request.POST.get('iridium_cep')
        data = request.POST.get('data')

        # Save the received message
        message = RockBlockMessage.objects.create(
            imei=imei,
            momsn=momsn,
            transmit_time=transmit_time,
            iridium_latitude=iridium_latitude,
            iridium_longitude=iridium_longitude,
            iridium_cep=iridium_cep,
            data=data
        )

        # Respond with success message
        return JsonResponse({'status': 'success'})

    # Respond with error for non-POST requests
    return JsonResponse({'error': 'Invalid request method'}, status=400)


def unescape_unicode(data):
    # Replace double backslashes with single backslashes
    data = data.replace('\\\\', '\\')

    try:
        # Unescape Unicode characters
        data = data.encode().decode('unicode-escape')
    except UnicodeDecodeError as e:
        # Handle the case where decoding fails
        print(f"Unicode decoding error: {e}")
        # You can choose to return an empty string or raise an exception here based on your application's logic
        return ""

    return data


def hex_decoder(hex_string):
    try:
        decoded_bytes = bytes.fromhex(hex_string)
        return decoded_bytes.decode('utf-8')
    except ValueError:
        return "Invalid hex string"


@api_view(["POST"])
def get_messages(request):
    request_data = json.loads(request.body)
    momsn_start = request_data.get('momsnStart')
    momsn_end = request_data.get('momsnEnd')

    # print(momsn_start,momsn_end)

    if momsn_start is not None and momsn_end is not None:
        messages = RockBlockMessage.objects.filter(momsn__range=(
            momsn_start, momsn_end)).order_by('momsn').values_list('data', flat=True)
    else:
        messages = None

    merged_data = ''.join(messages)
    decoded_data = hex_decoder(merged_data)

    # Write decoded data to JSON file without escaping characters
    with open('compressed_data.json', 'wb') as json_file:
        json_file.write(decoded_data.encode('utf-8'))

    # Call the function to process the uncompressed data
    T, F, Zxx_compressed_resized = process_compressed_data()

    # Convert processed data to JSON serializable format
    T_list = T.tolist()
    F_list = F.tolist()
    Zxx_compressed_resized_abs = np.abs(
        Zxx_compressed_resized)  # Take absolute values
    Zxx_compressed_resized_list = Zxx_compressed_resized_abs.tolist()

    # Send the processed data in the JSON response
    response_data = {
        'T': T_list,
        'F': F_list,
        'Zxx_compressed_resized': Zxx_compressed_resized_list
    }

    return JsonResponse(response_data)


def heatmap_view(request):
    return render(request, 'heatmap.html')


@api_view(["GET"])
def get_latest_message(request):
    try:
        # Retrieve the last row from the table
        last_message = RockBlockMessage.objects.latest('id')
        # Assuming 'id' is the primary key field, change it to the appropriate field name if needed

        response_data = {
            'id': last_message.id,
            'imei': last_message.imei,
            'momsn': last_message.momsn,
            'transmit_time': last_message.transmit_time,
        }

        return JsonResponse(response_data)
    except RockBlockMessage.DoesNotExist:
        # Handle the case where no messages exist in the table
        return JsonResponse({'error': 'No messages found'}, status=404)


def fetch_history(request):
    # Retrieve data from the database
    data = RockBlockMessage.objects.filter(
        momsn__in=[87, 95, 100, 121]).order_by('momsn', 'transmit_time')

    # Initialize variables
    momsn_start = None
    momsn_end = None
    transmit_start = None
    transmit_end = None
    result = []

    # Iterate through the data
    for item in data:
        # Set MOMSN start and transmit start for the current range
        if item.momsn == 87 or item.momsn == 100:
            momsn_start = item.momsn
            transmit_start = item.transmit_time
        # Set MOMSN end and transmit end for the current range
        elif item.momsn == 95 or item.momsn == 121:
            momsn_end = item.momsn
            transmit_end = item.transmit_time
            # Append the range to the result list
            result.append({
                'momsn_start': momsn_start,
                'momsn_end': momsn_end,
                'transmit_start': transmit_start,
                'transmit_end': transmit_end
            })
            # Reset variables for the next range
            momsn_start = None
            momsn_end = None
            transmit_start = None
            transmit_end = None

    # Serialize the result
    response_data = {'history': result}

    # Return the serialized data as JSON response
    return JsonResponse(response_data)
