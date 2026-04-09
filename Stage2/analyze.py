import xml.etree.ElementTree as ET

def analyze(file, nazwa):
    tree = ET.parse(file)
    pojazdy = tree.findall('tripinfo')

    durations = [float(t.get('duration')) for t in pojazdy]
    waiting = [float(t.get('waitingTime')) for t in pojazdy]

    print(f'\n=== {nazwa} ===')
    print(f'Liczba pojazdow (ukonczone):  {len(pojazdy)}')
    print(f'Sredni czas przejazdu:        {sum(durations)/len(durations):.2f} s')
    print(f'Sredni czas czekania:         {sum(waiting)/len(waiting):.2f} s')

analyze('output/tripinfo2.xml', 'Siec oryginalna')