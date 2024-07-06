import JDF_Classes as JC
import datetime

CreateMock = JC.JdfCasKod.CreateMock

#Rewritten Julia code into python
def SingleTestJdfFilter(trip:JC.JdfSpoj, day:datetime.date, expectedToOperate:bool):
    valid = JC.IsTripOperated(day, trip)
    if(valid == expectedToOperate):
        return
    print(f"JDF filter failed: Line {trip.CisloLinky} trip {trip.CisloSpoje}, version {trip.RozliseniLinky}, day {day}, expected answer {expectedToOperate}, filter reason:")
    print("unspecified")
    return

#test_jdf_filter(trip::Jdf.Trip, tests::Vector{Tuple{Date,Bool}}) = foreach(t->test_jdf_filter(trip, t[1], t[2]), tests)
def TestJdfFilter(trip,arglist):
    for a in arglist:
        SingleTestJdfFilter(trip,*a)

def TestJdfFilterPlzenArriva2020Mocks():
    """
    Test the trips as mocked with time codes
    """

    timeCodes = []
    trip = JC.CreateMockTrip(400621, 1, 3, [JC.DnyProvozu.PracovniDny], timeCodes, "15122019", "13122020")
    TestJdfFilter(trip, [ # Jede jen v pracovní dny
        (datetime.date(2020,6,29), True), # pondělí
        (datetime.date(2020,6,28), False), # neděle
        (datetime.date(2020,6,27), False), # sobota
        (datetime.date(2020,6,26), True), # pátek
        (datetime.date(2019,12,13), False), # před začátkem platnosti
        (datetime.date(2020,12,14), False), # po skončení platnosti
    ])

    #test_jdf_filter(trips_by_id[(400631,1,111)], [ # Jede jen v sobotu
    timeCodes = []
    trip = JC.CreateMockTrip(400631, 1, 111, [JC.DnyProvozu.Sobota], timeCodes, "15122019", "13122020")
    TestJdfFilter(trip, [ # Jede jen v pracovní dny
        (datetime.date(2020,6,29), False), # pondělí
        (datetime.date(2020,6,28), False), # neděle
        (datetime.date(2020,6,27), True), # sobota
        (datetime.date(2020,6,26), False), # pátek
    ])

    #test_jdf_filter(trips_by_id[(400631,1,109)], [ # jede v neděli a ve státem uznané svátky, nejede od 01.07.2020 do 31.08.2020, 27.09.2020, 28.10.2020, 17.11.2020
    timeCodes = [
        CreateMock(4,"01072020","31082020"),
        CreateMock(4,"27092020"),
        CreateMock(4,"28102020"),
        CreateMock(4,"17112020"),
                    ]
    trip = JC.CreateMockTrip(400631, 1, 109, [JC.DnyProvozu.Svatky], timeCodes, "15122019", "13122020")
    TestJdfFilter(trip, [ # jede v neděli a ve státem uznané svátky, nejede od 01.07.2020 do 31.08.2020, 27.09.2020, 28.10.2020, 17.11.2020
        (datetime.date(2020,6,29), False), # pondělí
        (datetime.date(2020,6,28), True), # neděle
        (datetime.date(2020,6,27), False), # sobota
        (datetime.date(2020,6,26), False), # pátek
        (datetime.date(2020,7,5), False), # neděle, svátek
        (datetime.date(2020,7,6), False), # pondělí, svátek
        (datetime.date(2020,7,27), False), # neděle
        (datetime.date(2020,10,28), False), # středa, svátek
        (datetime.date(2020,9,28), True), # pondělí, svátek
        (datetime.date(2020,9,27), False), # neděle
    ])

    #test_jdf_filter(trips_by_id[(400632,1,7)], [ # jede v pátek
    timeCodes = []
    trip = JC.CreateMockTrip(400632, 1, 7, [JC.DnyProvozu.Patek], timeCodes, "15122019", "31122020")
    TestJdfFilter(trip, [ # jede v pátek
        (datetime.date(2020,6,29), False), # pondělí
        (datetime.date(2020,6,28), False), # neděle
        (datetime.date(2020,6,27), False), # sobota
        (datetime.date(2020,6,26), True), # pátek
        (datetime.date(2020,6,25), False), # čtvrtek
        (datetime.date(2020,12,25), True), # pátek, svátek
    ])

    #test_jdf_filter(trips_by_id[(400632,1,9)], [ # jede v pondělí, středu a pátek, ale nejede 06.07.2020,28.09.2020,28.10.2020
    timeCodes = [
        CreateMock(4,"06072020"),
        CreateMock(4,"28092020"),
        CreateMock(4,"28102020"),
                    ]
    trip = JC.CreateMockTrip(400632, 1, 9, [JC.DnyProvozu.Pondeli, JC.DnyProvozu.Streda, JC.DnyProvozu.Patek], timeCodes, "15122019", "13122020")
    TestJdfFilter(trip, [ # jede v pondělí, středu a pátek, ale nejede 06.07.2020,28.09.2020,28.10.2020
        (datetime.date(2020,6,29), True), # pondělí
        (datetime.date(2020,6,28), False), # neděle
        (datetime.date(2020,6,27), False), # sobota
        (datetime.date(2020,6,26), True), # pátek
        (datetime.date(2020,6,25), False), # čtvrtek
        (datetime.date(2020,6,24), True), # středa
        (datetime.date(2020,6,23), False), # úterý
        (datetime.date(2020,7,6), False), # pondělí, svátek
        (datetime.date(2020,10,28), False), # středa, svátek
    ])

    #test_jdf_filter(trips_by_id[(400633,1,9)], [ # jede v pracovní dny
    timeCodes = []
    trip = JC.CreateMockTrip(400633, 1, 9, [JC.DnyProvozu.PracovniDny], timeCodes, "15122019", "13122020")
    TestJdfFilter(trip,[ # jede v pracovní dny
        (datetime.date(2020,6,29), True), # pondělí
        (datetime.date(2020,6,28), False), # neděle
        (datetime.date(2020,6,27), False), # sobota
        (datetime.date(2020,6,26), True), # pátek
        (datetime.date(2020,6,25), True), # čtvrtek
        (datetime.date(2020,6,24), True), # středa
        (datetime.date(2020,6,23), True), # úterý
        (datetime.date(2020,5,1), False), # pátek, svátek
        (datetime.date(2020,7,6), False), # pondělí, svátek
        (datetime.date(2020,10,28), False), # středa, svátek
        (datetime.date(2020,10,29), True), # čtvrtek
        (datetime.date(2020,7,23), True), # čtvrtek
        (datetime.date(2019,12,31), True), # úterý
    ])
    #test_jdf_filter(trips_by_id[(400633,1,25)], [ # jede v pracovní dny, nejede 31.12.2019
    timeCodes = [
        CreateMock(4,"31122019"),
                    ]
    trip = JC.CreateMockTrip(400633, 1, 25, [JC.DnyProvozu.PracovniDny], timeCodes, "15122019", "13122020")
    TestJdfFilter(trip, [ # jede v pracovní dny, nejede 31.12.2019
        (datetime.date(2020,6,29), True), # pondělí
        (datetime.date(2020,6,28), False), # neděle
        (datetime.date(2020,6,27), False), # sobota
        (datetime.date(2020,6,26), True), # pátek
        (datetime.date(2020,6,25), True), # čtvrtek
        (datetime.date(2020,6,24), True), # středa
        (datetime.date(2020,6,23), True), # úterý
        (datetime.date(2020,5,1), False), # pátek, svátek
        (datetime.date(2020,7,6), False), # pondělí, svátek
        (datetime.date(2020,10,28), False), # středa, svátek
        (datetime.date(2020,10,29), True), # čtvrtek
        (datetime.date(2020,7,23), True), # čtvrtek
        (datetime.date(2019,12,31), False), # úterý
    ])
    #test_jdf_filter(trips_by_id[(400633,1,101)], [ # jede v sobotu, jede v neděli a ve státem uznané svátky, nejede 25.12.2019, 1.1.2020
    timeCodes = []
    timeCodes.append(JC.JdfCasKod.CreateMock(4,"25122019"))
    timeCodes.append(JC.JdfCasKod.CreateMock(4,"01012020"))
    trip = JC.CreateMockTrip(400633, 1, 101, [JC.DnyProvozu.Sobota, JC.DnyProvozu.Svatky], timeCodes, "15122019", "13122020")
    TestJdfFilter(trip, [ # jede v sobotu, jede v neděli a ve státem uznané svátky, nejede 25.12.2019, 1.1.2020
        (datetime.date(2020,6,29), False), # pondělí
        (datetime.date(2020,6,28), True), # neděle
        (datetime.date(2020,6,27), True), # sobota
        (datetime.date(2020,6,26), False), # pátek
        (datetime.date(2020,6,25), False), # čtvrtek
        (datetime.date(2020,6,24), False), # středa
        (datetime.date(2020,6,23), False), # úterý
        (datetime.date(2020,5,1), True), # pátek, svátek
        (datetime.date(2020,7,6), True), # pondělí, svátek
        (datetime.date(2020,10,28), True), # středa, svátek
        (datetime.date(2020,10,29), False), # čtvrtek
        (datetime.date(2020,7,23), False), # čtvrtek
        (datetime.date(2019,12,31), False), # úterý
        (datetime.date(2019,12,25), False), # středa
        (datetime.date(2020,1,1), False), # středa, svátek
    ])
    #test_jdf_filter(trips_by_id[(490750,1,21)], [ # jede v pondělí a ve středu, jede od 1.7.2020 do 31.8.2020, jede od 28.10.2020 do 30.10.2020, nejede 6.7.2020, nejede 28.10.2020
    timeCodes = [
        CreateMock(1,"01072020","31082020"),
        CreateMock(1,"28102020","30102020"),
        CreateMock(4,"06072020"),
        CreateMock(4,"28102020"),
                    ]
    trip = JC.CreateMockTrip(490750, 1, 21, [JC.DnyProvozu.Pondeli, JC.DnyProvozu.Streda], timeCodes, "15122019", "13122020")
    TestJdfFilter(trip, [ # jede v pondělí a ve středu, jede od 1.7.2020 do 31.8.2020, jede od 28.10.2020 do 30.10.2020, nejede 6.7.2020, nejede 28.10.2020
        (datetime.date(2020,6,23), False), # úterý
        (datetime.date(2020,6,24), False), # středa
        (datetime.date(2020,6,25), False), # čtvrtek
        (datetime.date(2020,6,26), False), # pátek
        (datetime.date(2020,6,27), False), # sobota
        (datetime.date(2020,6,28), False), # neděle
        (datetime.date(2020,6,29), False), # pondělí
        (datetime.date(2020,6,30), False), # úterý
        (datetime.date(2020,7,1), True), # středa
        (datetime.date(2020,7,2), False), # čtvrtek
        (datetime.date(2020,7,3), False), # pátek
        (datetime.date(2020,7,4), False), # sobota
        (datetime.date(2020,7,5), False), # neděle
        (datetime.date(2020,7,6), False), # pondělí, svátek
        (datetime.date(2020,7,7), False), # úterý
        (datetime.date(2020,7,8), True), # středa
        (datetime.date(2020,10,28), False), # středa, svátek
        (datetime.date(2020,10,29), False), # čtvrtek
        (datetime.date(2020,10,30), False), # pátek
    ])
    #test_jdf_filter(trips_by_id[(490750,1,23)], [ # jede v pracovních dnech, nejede od 1.7.2020 do 31.8.2020, nejede od 28.10.2020 do 30.10.2020
    timeCodes = [
        CreateMock(4,"01072020","31082020"),
        CreateMock(4,"28102020","30102020"),
                    ]
    trip = JC.CreateMockTrip(490750, 1, 23, [JC.DnyProvozu.PracovniDny], timeCodes, "15122019", "13122020")
    TestJdfFilter(trip, [ # jede v pracovních dnech, nejede od 1.7.2020 do 31.8.2020, nejede od 28.10.2020 do 30.10.2020
        (datetime.date(2020,6,23), True), # úterý
        (datetime.date(2020,6,24), True), # středa
        (datetime.date(2020,6,25), True), # čtvrtek
        (datetime.date(2020,6,26), True), # pátek
        (datetime.date(2020,6,27), False), # sobota
        (datetime.date(2020,6,28), False), # neděle
        (datetime.date(2020,6,29), True), # pondělí
        (datetime.date(2020,6,30), True), # úterý
        (datetime.date(2020,7,1), False), # středa
        (datetime.date(2020,7,2), False), # čtvrtek
        (datetime.date(2020,7,3), False), # pátek
        (datetime.date(2020,7,4), False), # sobota
        (datetime.date(2020,7,5), False), # neděle
        (datetime.date(2020,7,6), False), # pondělí, svátek
        (datetime.date(2020,7,7), False), # úterý
        (datetime.date(2020,7,8), False), # středa
        (datetime.date(2020,10,28), False), # středa, svátek
        (datetime.date(2020,10,29), False), # čtvrtek
        (datetime.date(2020,10,30), False), # pátek
    ])
    #test_jdf_filter(trips_by_id[(440251,1,45)], [ # jede v sobotu, neděli a ve státem uznané svátky, jede od 14.6.2020 do 28.9.2020
    timeCodes = [
        CreateMock(1,"14062020","28092020"),
        #CreateMock(4,"28102020","30102020"),
                    ]
    trip = JC.CreateMockTrip(440251, 1, 45, [JC.DnyProvozu.Sobota, JC.DnyProvozu.Svatky], timeCodes, "15122019", "13122020")
    TestJdfFilter(trip, [ # jede v sobotu, neděli a ve státem uznané svátky, jede od 14.6.2020 do 28.9.2020
        (datetime.date(2020,6,23), False), # úterý
        (datetime.date(2020,6,24), False), # středa
        (datetime.date(2020,6,25), False), # čtvrtek
        (datetime.date(2020,6,26), False), # pátek
        (datetime.date(2020,6,27), True), # sobota
        (datetime.date(2020,6,28), True), # neděle
        (datetime.date(2020,6,29), False), # pondělí
        (datetime.date(2020,6,30), False), # úterý
        (datetime.date(2020,7,1), False), # středa
        (datetime.date(2020,7,2), False), # čtvrtek
        (datetime.date(2020,7,3), False), # pátek
        (datetime.date(2020,7,4), True), # sobota
        (datetime.date(2020,7,5), True), # neděle
        (datetime.date(2020,7,6), True), # pondělí, svátek
        (datetime.date(2020,7,7), False), # úterý
        (datetime.date(2020,7,8), False), # středa
        (datetime.date(2020,9,28), True), # pondělí, svátek
        (datetime.date(2020,9,29), False), # úterý
        (datetime.date(2020,10,28), False), # středa, svátek
        (datetime.date(2020,10,29), False), # čtvrtek
        (datetime.date(2020,10,30), False), # pátek
    ])
    #test_jdf_filter(trips_by_id[(400639,1,7)], [ # jede v pondělí a ve středu, jede od 23.12.2019 do 3.1.2020, 
    #od 17.2.2020 do 23.2.2020, od 9.4.2020 do 13.4.2020, od 1.7.2020 do 31.8.2020, od 28.10.2020 do 30.10.2020, 
    #nejede 25.12.2019,1.1.2020,13.4.2020,6.7.2020,28.10.2020
    timeCodes = [
        CreateMock(1,"23122019","03012020"),
        CreateMock(1,"17022020","23022020"),
        CreateMock(1,"09042020","13042020"),
        CreateMock(1,"01072020","31082020"),
        CreateMock(1,"28102020","30102020"),
        CreateMock(4,"25122019"),
        CreateMock(4,"01012020"),
        CreateMock(4,"13042020"),
        CreateMock(4,"06072020"),
        CreateMock(4,"28102020"),
                    ]
    trip = JC.CreateMockTrip(400639, 1, 7, [JC.DnyProvozu.Pondeli, JC.DnyProvozu.Streda], timeCodes, "15122019", "13122020")
    TestJdfFilter(trip,[ # jede v pondělí a ve středu, jede od 23.12.2019 do 3.1.2020, od 17.2.2020 do 23.2.2020, od 9.4.2020 do 13.4.2020, od 1.7.2020 do 31.8.2020, od 28.10.2020 do 30.10.2020, nejede 25.12.2019,1.1.2020,13.4.2020,6.7.2020,28.10.2020
        (datetime.date(2020,6,29), False), # pondělí
        (datetime.date(2020,6,28), False), # neděle
        (datetime.date(2020,6,27), False), # sobota
        (datetime.date(2020,6,26), False), # pátek
        (datetime.date(2020,6,25), False), # čtvrtek
        (datetime.date(2020,6,24), False), # středa
        (datetime.date(2020,6,23), False), # úterý
        (datetime.date(2020,7,1), True), # středa
        (datetime.date(2020,7,2), False), # čtvrtek
        (datetime.date(2020,7,3), False), # pátek
        (datetime.date(2020,7,4), False), # sobota
        (datetime.date(2020,7,5), False), # neděle
        (datetime.date(2020,7,6), False), # pondělí, svátek
        (datetime.date(2020,7,20), True), # pondělí
        (datetime.date(2020,7,23), False), # čtvrtek
        (datetime.date(2020,10,28), False), # středa, svátek
        (datetime.date(2020,10,29), False), # čtvrtek

    ])
    #test_jdf_filter(trips_by_id[(400641,1,6)], [ # jede v pracovních dnech, jede od 23.12.2019 do 3.1.2020,31.1.2020, 
    #od 17.2.2020 do 23.2.2020, od 9.4.2020 do 13.4.2020, od 1.7.2020 do 31.8.2020, od 28.10.2020 do 30.10.2020
    timeCodes = [
        CreateMock(1,"23122019","03012020"),
        CreateMock(1,"31012020"),
        CreateMock(1,"17022020","23022020"),
        CreateMock(1,"09042020","13042020"),
        CreateMock(1,"01072020","31082020"),
        CreateMock(1,"28102020","30102020"),
                    ]
    trip = JC.CreateMockTrip(400641, 1, 6, [JC.DnyProvozu.PracovniDny], timeCodes, "15122019", "13122020")
    TestJdfFilter(trip, [ # jede v pracovních dnech, jede od 23.12.2019 do 3.1.2020,31.1.2020, od 17.2.2020 do 23.2.2020, od 9.4.2020 do 13.4.2020, od 1.7.2020 do 31.8.2020, od 28.10.2020 do 30.10.2020
        (datetime.date(2020,6,23), False), # úterý
        (datetime.date(2020,6,24), False), # středa
        (datetime.date(2020,6,25), False), # čtvrtek
        (datetime.date(2020,6,26), False), # pátek
        (datetime.date(2020,6,27), False), # sobota
        (datetime.date(2020,6,28), False), # neděle
        (datetime.date(2020,6,29), False), # pondělí
        (datetime.date(2020,6,30), False), # úterý
        (datetime.date(2020,7,1), True), # středa
        (datetime.date(2020,7,2), True), # čtvrtek
        (datetime.date(2020,7,3), True), # pátek
        (datetime.date(2020,7,4), False), # sobota
        (datetime.date(2020,7,5), False), # neděle
        (datetime.date(2020,7,6), False), # pondělí, svátek
        (datetime.date(2020,7,7), True), # úterý
        (datetime.date(2020,7,8), True), # středa
        (datetime.date(2020,9,28), False), # pondělí, svátek
        (datetime.date(2020,9,29), False), # úterý
        (datetime.date(2020,10,28), False), # středa, svátek
        (datetime.date(2020,10,29), True), # čtvrtek
        (datetime.date(2020,10,30), True), # pátek
    ])

    #test_jdf_filter(trips_by_id[(490737,1,5)], [ # jede v pracovních dnech a v neděli, jede také 6.7.2020, jede také 28.9.2020, 
    #jede také 28.10.2020, jede také 17.11.2020,
    #nejede 5.7.2020, nejede 27.9.2020, nejede 27.10.2020, nejede 16.11.2020
    timeCodes = [
        CreateMock(2,"06072020"),
        CreateMock(2,"28092020"),
        CreateMock(2,"28102020"),
        CreateMock(2,"17112020"),
        CreateMock(4,"05072020"),
        CreateMock(4,"27092020"),
        CreateMock(4,"27102020"),
        CreateMock(4,"16112020"),
                    ]
    trip = JC.CreateMockTrip(490737, 1, 5, [JC.DnyProvozu.PracovniDny, JC.DnyProvozu.Nedele], timeCodes, "15122019", "13122020")
    TestJdfFilter(trip, [ # jede v pracovních dnech a v neděli, jede také 6.7.2020, jede také 28.9.2020, jede také 28.10.2020, jede také 17.11.2020, nejede 5.7.2020, nejede 27.9.2020, nejede 27.10.2020, nejede 16.11.2020
        (datetime.date(2020,6,23), True), # úterý
        (datetime.date(2020,6,24), True), # středa
        (datetime.date(2020,6,25), True), # čtvrtek
        (datetime.date(2020,6,26), True), # pátek
        (datetime.date(2020,6,27), False), # sobota
        (datetime.date(2020,6,28), True), # neděle
        (datetime.date(2020,6,29), True), # pondělí
        (datetime.date(2020,6,30), True), # úterý
        (datetime.date(2020,7,1), True), # středa
        (datetime.date(2020,7,2), True), # čtvrtek
        (datetime.date(2020,7,3), True), # pátek
        (datetime.date(2020,7,4), False), # sobota
        (datetime.date(2020,7,5), False), # neděle
        (datetime.date(2020,7,6), True), # pondělí, svátek
        (datetime.date(2020,7,7), True), # úterý
        (datetime.date(2020,7,8), True), # středa
        (datetime.date(2020,9,27), False), # neděle
        (datetime.date(2020,9,28), True), # pondělí, svátek
        (datetime.date(2020,9,29), True), # úterý
        (datetime.date(2020,10,28), True), # středa, svátek
        (datetime.date(2020,10,29), True), # čtvrtek
        (datetime.date(2020,10,30), True), # pátek
    ])


def TestJdfFilterPlzenArriva2020():
    """
    Test the trips as they are in the actual JDF
    """
    LoadedJDF = JC.ParseSingleFolder("../SharedData/JDF_Data/Arriva_804")
    if not LoadedJDF:
        print ("Error, could not find")
    trips_by_id = LoadedJDF.JdfSpoje

    TestJdfFilter(trips_by_id[(400621,1,3)], [ # Jede jen v pracovní dny
        (datetime.date(2020,6,29), True), # pondělí
        (datetime.date(2020,6,28), False), # neděle
        (datetime.date(2020,6,27), False), # sobota
        (datetime.date(2020,6,26), True), # pátek
        (datetime.date(2019,12,13), False), # před začátkem platnosti
        (datetime.date(2020,12,14), False), # po skončení platnosti
    ])

    TestJdfFilter(trips_by_id[(400631,1,111)], [ # Jede jen v sobotu
        (datetime.date(2020,6,29), False), # pondělí
        (datetime.date(2020,6,28), False), # neděle
        (datetime.date(2020,6,27), True), # sobota
        (datetime.date(2020,6,26), False), # pátek
    ])

    TestJdfFilter(trips_by_id[(400631,1,109)], [ # jede v neděli a ve státem uznané svátky, nejede od 01.07.2020 do 31.08.2020, 27.09.2020, 28.10.2020, 17.11.2020
        (datetime.date(2020,6,29), False), # pondělí
        (datetime.date(2020,6,28), True), # neděle
        (datetime.date(2020,6,27), False), # sobota
        (datetime.date(2020,6,26), False), # pátek
        (datetime.date(2020,7,5), False), # neděle, svátek
        (datetime.date(2020,7,6), False), # pondělí, svátek
        (datetime.date(2020,7,27), False), # neděle
        (datetime.date(2020,10,28), False), # středa, svátek
        (datetime.date(2020,9,28), True), # pondělí, svátek
        (datetime.date(2020,9,27), False), # neděle
    ])

    TestJdfFilter(trips_by_id[(400632,1,7)], [ # jede v pátek
        (datetime.date(2020,6,29), False), # pondělí
        (datetime.date(2020,6,28), False), # neděle
        (datetime.date(2020,6,27), False), # sobota
        (datetime.date(2020,6,26), True), # pátek
        (datetime.date(2020,6,25), False), # čtvrtek
        (datetime.date(2020,12,25), True), # pátek, svátek
    ])

    TestJdfFilter(trips_by_id[(400632,1,9)], [ # jede v pondělí, středu a pátek, ale nejede 06.07.2020,28.09.2020,28.10.2020
        (datetime.date(2020,6,29), True), # pondělí
        (datetime.date(2020,6,28), False), # neděle
        (datetime.date(2020,6,27), False), # sobota
        (datetime.date(2020,6,26), True), # pátek
        (datetime.date(2020,6,25), False), # čtvrtek
        (datetime.date(2020,6,24), True), # středa
        (datetime.date(2020,6,23), False), # úterý
        (datetime.date(2020,7,6), False), # pondělí, svátek
        (datetime.date(2020,10,28), False), # středa, svátek
    ])

    TestJdfFilter(trips_by_id[(400633,1,9)], [ # jede v pracovní dny
        (datetime.date(2020,6,29), True), # pondělí
        (datetime.date(2020,6,28), False), # neděle
        (datetime.date(2020,6,27), False), # sobota
        (datetime.date(2020,6,26), True), # pátek
        (datetime.date(2020,6,25), True), # čtvrtek
        (datetime.date(2020,6,24), True), # středa
        (datetime.date(2020,6,23), True), # úterý
        (datetime.date(2020,5,1), False), # pátek, svátek
        (datetime.date(2020,7,6), False), # pondělí, svátek
        (datetime.date(2020,10,28), False), # středa, svátek
        (datetime.date(2020,10,29), True), # čtvrtek
        (datetime.date(2020,7,23), True), # čtvrtek
        (datetime.date(2019,12,31), True), # úterý
    ])
    TestJdfFilter(trips_by_id[(400633,1,25)], [ # jede v pracovní dny, nejede 31.12.2019
        (datetime.date(2020,6,29), True), # pondělí
        (datetime.date(2020,6,28), False), # neděle
        (datetime.date(2020,6,27), False), # sobota
        (datetime.date(2020,6,26), True), # pátek
        (datetime.date(2020,6,25), True), # čtvrtek
        (datetime.date(2020,6,24), True), # středa
        (datetime.date(2020,6,23), True), # úterý
        (datetime.date(2020,5,1), False), # pátek, svátek
        (datetime.date(2020,7,6), False), # pondělí, svátek
        (datetime.date(2020,10,28), False), # středa, svátek
        (datetime.date(2020,10,29), True), # čtvrtek
        (datetime.date(2020,7,23), True), # čtvrtek
        (datetime.date(2019,12,31), False), # úterý
    ])
    TestJdfFilter(trips_by_id[(400633,1,101)], [ # jede v sobotu, jede v neděli a ve státem uznané svátky, nejede 25.12.2019, 1.1.2020
        (datetime.date(2020,6,29), False), # pondělí
        (datetime.date(2020,6,28), True), # neděle
        (datetime.date(2020,6,27), True), # sobota
        (datetime.date(2020,6,26), False), # pátek
        (datetime.date(2020,6,25), False), # čtvrtek
        (datetime.date(2020,6,24), False), # středa
        (datetime.date(2020,6,23), False), # úterý
        (datetime.date(2020,5,1), True), # pátek, svátek
        (datetime.date(2020,7,6), True), # pondělí, svátek
        (datetime.date(2020,10,28), True), # středa, svátek
        (datetime.date(2020,10,29), False), # čtvrtek
        (datetime.date(2020,7,23), False), # čtvrtek
        (datetime.date(2019,12,31), False), # úterý
        (datetime.date(2019,12,25), False), # středa
        (datetime.date(2020,1,1), False), # středa, svátek
    ])
    TestJdfFilter(trips_by_id[(490750,1,21)], [ # jede v pondělí a ve středu, jede od 1.7.2020 do 31.8.2020, jede od 28.10.2020 do 30.10.2020, nejede 6.7.2020, nejede 28.10.2020
        (datetime.date(2020,6,23), False), # úterý
        (datetime.date(2020,6,24), False), # středa
        (datetime.date(2020,6,25), False), # čtvrtek
        (datetime.date(2020,6,26), False), # pátek
        (datetime.date(2020,6,27), False), # sobota
        (datetime.date(2020,6,28), False), # neděle
        (datetime.date(2020,6,29), False), # pondělí
        (datetime.date(2020,6,30), False), # úterý
        (datetime.date(2020,7,1), True), # středa
        (datetime.date(2020,7,2), False), # čtvrtek
        (datetime.date(2020,7,3), False), # pátek
        (datetime.date(2020,7,4), False), # sobota
        (datetime.date(2020,7,5), False), # neděle
        (datetime.date(2020,7,6), False), # pondělí, svátek
        (datetime.date(2020,7,7), False), # úterý
        (datetime.date(2020,7,8), True), # středa
        (datetime.date(2020,10,28), False), # středa, svátek
        (datetime.date(2020,10,29), False), # čtvrtek
        (datetime.date(2020,10,30), False), # pátek
    ])
    TestJdfFilter(trips_by_id[(490750,1,23)], [ # jede v pracovních dnech, nejede od 1.7.2020 do 31.8.2020, nejede od 28.10.2020 do 30.10.2020
        (datetime.date(2020,6,23), True), # úterý
        (datetime.date(2020,6,24), True), # středa
        (datetime.date(2020,6,25), True), # čtvrtek
        (datetime.date(2020,6,26), True), # pátek
        (datetime.date(2020,6,27), False), # sobota
        (datetime.date(2020,6,28), False), # neděle
        (datetime.date(2020,6,29), True), # pondělí
        (datetime.date(2020,6,30), True), # úterý
        (datetime.date(2020,7,1), False), # středa
        (datetime.date(2020,7,2), False), # čtvrtek
        (datetime.date(2020,7,3), False), # pátek
        (datetime.date(2020,7,4), False), # sobota
        (datetime.date(2020,7,5), False), # neděle
        (datetime.date(2020,7,6), False), # pondělí, svátek
        (datetime.date(2020,7,7), False), # úterý
        (datetime.date(2020,7,8), False), # středa
        (datetime.date(2020,10,28), False), # středa, svátek
        (datetime.date(2020,10,29), False), # čtvrtek
        (datetime.date(2020,10,30), False), # pátek
    ])
    TestJdfFilter(trips_by_id[(440251,1,45)], [ # jede v sobotu, neděli a ve státem uznané svátky, jede od 14.6.2020 do 28.9.2020
        (datetime.date(2020,6,23), False), # úterý
        (datetime.date(2020,6,24), False), # středa
        (datetime.date(2020,6,25), False), # čtvrtek
        (datetime.date(2020,6,26), False), # pátek
        (datetime.date(2020,6,27), True), # sobota
        (datetime.date(2020,6,28), True), # neděle
        (datetime.date(2020,6,29), False), # pondělí
        (datetime.date(2020,6,30), False), # úterý
        (datetime.date(2020,7,1), False), # středa
        (datetime.date(2020,7,2), False), # čtvrtek
        (datetime.date(2020,7,3), False), # pátek
        (datetime.date(2020,7,4), True), # sobota
        (datetime.date(2020,7,5), True), # neděle
        (datetime.date(2020,7,6), True), # pondělí, svátek
        (datetime.date(2020,7,7), False), # úterý
        (datetime.date(2020,7,8), False), # středa
        (datetime.date(2020,9,28), True), # pondělí, svátek
        (datetime.date(2020,9,29), False), # úterý
        (datetime.date(2020,10,28), False), # středa, svátek
        (datetime.date(2020,10,29), False), # čtvrtek
        (datetime.date(2020,10,30), False), # pátek
    ])
    TestJdfFilter(trips_by_id[(400639,1,7)], [ # jede v pondělí a ve středu, jede od 23.12.2019 do 3.1.2020, 
    #od 17.2.2020 do 23.2.2020, od 9.4.2020 do 13.4.2020, od 1.7.2020 do 31.8.2020, od 28.10.2020 do 30.10.2020, 
    #nejede 25.12.2019,1.1.2020,13.4.2020,6.7.2020,28.10.2020
        (datetime.date(2020,6,29), False), # pondělí
        (datetime.date(2020,6,28), False), # neděle
        (datetime.date(2020,6,27), False), # sobota
        (datetime.date(2020,6,26), False), # pátek
        (datetime.date(2020,6,25), False), # čtvrtek
        (datetime.date(2020,6,24), False), # středa
        (datetime.date(2020,6,23), False), # úterý
        (datetime.date(2020,7,1), True), # středa
        (datetime.date(2020,7,2), False), # čtvrtek
        (datetime.date(2020,7,3), False), # pátek
        (datetime.date(2020,7,4), False), # sobota
        (datetime.date(2020,7,5), False), # neděle
        (datetime.date(2020,7,6), False), # pondělí, svátek
        (datetime.date(2020,7,20), True), # pondělí
        (datetime.date(2020,7,23), False), # čtvrtek
        (datetime.date(2020,10,28), False), # středa, svátek
        (datetime.date(2020,10,29), False), # čtvrtek

    ])
    TestJdfFilter(trips_by_id[(400641,1,6)], [ # jede v pracovních dnech, jede od 23.12.2019 do 3.1.2020,31.1.2020, 
    #od 17.2.2020 do 23.2.2020, od 9.4.2020 do 13.4.2020, od 1.7.2020 do 31.8.2020, od 28.10.2020 do 30.10.2020
        (datetime.date(2020,6,23), False), # úterý
        (datetime.date(2020,6,24), False), # středa
        (datetime.date(2020,6,25), False), # čtvrtek
        (datetime.date(2020,6,26), False), # pátek
        (datetime.date(2020,6,27), False), # sobota
        (datetime.date(2020,6,28), False), # neděle
        (datetime.date(2020,6,29), False), # pondělí
        (datetime.date(2020,6,30), False), # úterý
        (datetime.date(2020,7,1), True), # středa
        (datetime.date(2020,7,2), True), # čtvrtek
        (datetime.date(2020,7,3), True), # pátek
        (datetime.date(2020,7,4), False), # sobota
        (datetime.date(2020,7,5), False), # neděle
        (datetime.date(2020,7,6), False), # pondělí, svátek
        (datetime.date(2020,7,7), True), # úterý
        (datetime.date(2020,7,8), True), # středa
        (datetime.date(2020,9,28), False), # pondělí, svátek
        (datetime.date(2020,9,29), False), # úterý
        (datetime.date(2020,10,28), False), # středa, svátek
        (datetime.date(2020,10,29), True), # čtvrtek
        (datetime.date(2020,10,30), True), # pátek
    ])

    TestJdfFilter(trips_by_id[(490737,1,5)], [ # jede v pracovních dnech a v neděli, jede také 6.7.2020, jede také 28.9.2020, 
    #jede také 28.10.2020, jede také 17.11.2020,
    #nejede 5.7.2020, nejede 27.9.2020, nejede 27.10.2020, nejede 16.11.2020
        (datetime.date(2020,6,23), True), # úterý
        (datetime.date(2020,6,24), True), # středa
        (datetime.date(2020,6,25), True), # čtvrtek
        (datetime.date(2020,6,26), True), # pátek
        (datetime.date(2020,6,27), False), # sobota
        (datetime.date(2020,6,28), True), # neděle
        (datetime.date(2020,6,29), True), # pondělí
        (datetime.date(2020,6,30), True), # úterý
        (datetime.date(2020,7,1), True), # středa
        (datetime.date(2020,7,2), True), # čtvrtek
        (datetime.date(2020,7,3), True), # pátek
        (datetime.date(2020,7,4), False), # sobota
        (datetime.date(2020,7,5), False), # neděle
        (datetime.date(2020,7,6), True), # pondělí, svátek
        (datetime.date(2020,7,7), True), # úterý
        (datetime.date(2020,7,8), True), # středa
        (datetime.date(2020,9,27), False), # neděle
        (datetime.date(2020,9,28), True), # pondělí, svátek
        (datetime.date(2020,9,29), True), # úterý
        (datetime.date(2020,10,28), True), # středa, svátek
        (datetime.date(2020,10,29), True), # čtvrtek
        (datetime.date(2020,10,30), True), # pátek
    ])
    # Try all trips and dates
    startDate = datetime.date(2020, 12, 12)
    endDate = datetime.date(2020, 12, 12)
    delta = datetime.timedelta(days=1)

    while(startDate <= endDate):
        print(startDate)
        print("")
        for trip in LoadedJDF.JdfSpoje.values():
            if JC.IsTripOperated(startDate, trip, LoadedJDF.JdfLinky):
                print(trip)
                print("")
    startDate += delta

def main():
    TestJdfFilterPlzenArriva2020()


if __name__ == "__main__":
    main()
